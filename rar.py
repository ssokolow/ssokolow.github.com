#!/usr/bin/env python
"""
A pure-Python module for identifying and examining RAR files developed without
any exposure to the original unrar code. (Just format docs from www.wotsit.org)

TODO:
- Document this module properly.
- Complete the parsing of the RAR metadata.
  (eg. Identify directories, check CRCs, etc.)
- Make sure this has the same coding and error conventions as my gif.py.
- Consider releasing this under PSF 2.3 license instead.
- Support extraction of files stored with no compression. (eg. XviD movies)
- Look into supporting split and password-protected RARs
"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.2"
__license__ = "GPL 2 or later"
__revision__ = "$Revision$"

# Settings for _find_header()
CHUNK_SIZE = 4096
MARKER_BLOCK = "\x52\x61\x72\x21\x1a\x07\x00"
FIND_LIMIT = 1024**2 # 1MiB
# A Compromise. Override FIND_LIMIT with 0 to be sure but very slow.

_struct_blockHeader = "<HBHH"
_struct_fileHead_add1 = "<LBLLBBHL" # Plus FILE_NAME and everything after it

block_types = {
	0x72: 'MARK_HEAD',
	0x73: 'MAIN_HEAD',
	0x74: 'File Header',
	0x75: 'Comment Header',
	0x76: 'Extra Info',
	0x77: 'Subblock',
	0x78: 'Recovery Record',
	0x7b: 'Terminator?'
}

os_map = {
	0: 'MS DOS',
	1: 'OS/2',
	2: 'Win32',
	3: 'Unix',
}

import math, struct, sys, zlib

class BadRarFile(Exception):
	"""The error raised for bad RAR files."""
	pass

def _read_struct(fmt, handle):
	"""Simplifies the process of extracting a struct from a file handle.
	Just takes a struct format string and a properly-seeked file handle.
	"""
	return struct.unpack(fmt, handle.read(struct.calcsize(fmt)))

def _find_header(handle, limit=FIND_LIMIT):
	"""Searches a file-like object for a RAR header.
	
	Returns the in-file offset of the first byte after the header block
	or None if no RAR header was found.
	
	Note: limit is rounded up to the nearest multiple of CHUNK_SIZE.
	"""
	chunk = ""
	limit = math.ceil(limit / float(CHUNK_SIZE)) * CHUNK_SIZE

	# Find the RAR header and line up for further reads. (Support SFX bundles)
	while True:
		temp = handle.read(CHUNK_SIZE)

		# If we hit the end of the file without finding a RAR marker block...
		if not temp or (limit > 0 and handle.tell() > limit):
			return None

		chunk += temp
		marker_offset = chunk.find(MARKER_BLOCK)
		if marker_offset > -1:
			return handle.tell() - len(chunk) + marker_offset + len(MARKER_BLOCK)

		# Obviously we haven't found the marker yet...
		chunk = chunk[len(temp):] # Use a rolling window to minimize memory consumption.

def _check_crc(data, crc):
	"""Check some data against a stored CRC.
	
	Note: For header CRCs, RAR calculates a CRC32 and then throws out the high-order bytes.
	
	TODO: I've only tested this out on 2-byte CRCs, not 4-byte file data CRCs.
	FIXME: Figure out why I can't get a match on valid File Header CRCs.
	TODO: Isn't there some better way to do the check for CRC bitwidth?
	"""
	if isinstance(crc, int):
		if crc < 65536:
			crc = struct.pack('>H', crc)
		else:
			crc = struct.pack('>L', crc)
	return struct.pack('>L',zlib.crc32(data)).endswith(crc)

def is_rarfile(filename, limit=FIND_LIMIT):
	"""Returns True if filename is a valid RAR file based on its magic number, otherwise returns False.
	
	Optionally takes a limiting value for the maximum amount of data to sift through.
	Defaults to 1MiB to set a sane bound on performance. Set it to 0 to perform an
	exhaustive search for a RAR header.
	Note: _find_header rounds this limit up to the nearest multiple of CHUNK_SIZE.
	"""
	try:
		handle = file(filename, 'rb')
		return bool(_find_header(handle, limit))
	except Exception:
		return False

def list_rar(fp, limit=FIND_LIMIT):
	# Skip the SFX module if present
	start_offset = _find_header(fp, limit)

	if start_offset: fp.seek(start_offset)
	else: raise BadRarFile("Not a valid RAR file")

	contents = []
	while True: # Each iteration reads one block
		offset = fp.tell()
		try:
			head_crc, head_type, head_flags, head_size = _read_struct(_struct_blockHeader, fp)
		except:
			# If it fails here, we've reached the end of the file.
			return contents

		if head_flags & 0x8000:
			add_size = _read_struct('<L', fp)[0]
		else:
			add_size = 0

		if head_type == 0x73:
			fp.seek(offset + 2) # Seek to just after HEAD_CRC
			#FIXME: Don't assert... except.
			assert _check_crc(fp.read(11), head_crc)
			
		elif head_type == 0x74:
			pack_size = add_size
			unp_size, host_os, file_crc, ftime, unp_ver, method, name_size, attr = _read_struct(_struct_fileHead_add1, fp)
			
			# FIXME: What encoding does WinRAR use for filenames?
			contents.append(fp.read(name_size))
		else:
			print "Unhandled block: %s" % block_types.get(head_type, 'Unknown (%s)' % head_type)
		
		# Line up for the next block
		fp.seek(offset + head_size + add_size)

if __name__ == '__main__':
	for arg in sys.argv[1:]:
		print "File: %s" % arg
		if is_rarfile(arg):
			for line in list_rar(file(arg)):
				print "\t%s" % line
		else:
			print "Not a RAR file"
