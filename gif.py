#!/usr/bin/env python
"""
By: Stephan Sokolow (deitarion/SSokolow)
A pure Python GIF validator which also counts the number of frames.
Originally conceived as simiply a static/animated detector.

TODO:
- Clean up and reorganize the code some more.
- Validate whatever I can in the color table and the other bit flags.
- Find other things I can validate.
- Provide a function to extract a GIF's comment blocks.
"""

# check types (TODO: Confirm this is the proper way and then implement them)
CHECK_IS_GIF_FILE  = 0 # Just check for a valid GIF header.
CHECK_IS_ANIMATED  = 1 # Check whether the file has more than one frame.
CHECK_COUNT_FRAMES = 2 # Count the number of frames in the file.
CHECK_VRFY_DIMENS  = 4 # Verify that the screen descriptor-specified dimensions are bigger than max(frame sizes)
CHECK_INF_LOOPING  = 8 # Test whether the gif loops indefinitely or stops after a period of time. (and whether only a part loops)

# error/exit codes (returned by the check function)
ERR_NONE = 0 # All is well. The image is a GIF that is a prime candidate for PNGing. (but don't forget to copy XMP metadata)
ERR_HDR  = 1 # Not a valid GIF file. (Invalid header)
ERR_EOF  = 2 # File is missing it's trailer. (Probably either corrupt elsewhere, truncated, or breaking spec by using EOF as the terminator.)

# warning codes (second part of the returned tuple)
WARN_NONE = 0    # No warnings
WARN_BAD_IMG = 1 # Corruption (of the [sub]block size field(s)) or truncation detected in an image block
WARN_BAD_EXT = 2 # Corruption (of the [sub]block size field(s)) or truncation detected in an extension block

import os, sys

def check_gif(fh):
	"""Takes a file-like object, returns an (error, warnings, frame count, error message) tuple.

	Can also be used to walk past a valid GIF file in an un-delimited byte stream in order 
	to identify the point at which the following file starts. (It doesn't fh.seek(0) or fh.close()
	after use)"""
	def skipColorTable(fields, handle):
		#TODO: Verify correctness.
		if ord(fields) & int("10000000", 2):
			nBits = ord(fields) & int("00000111", 2)
			tableSize = 3 * 2**( nBits + 1 )
			handle.seek( handle.tell() + tableSize )

	def skipSubBlocks(handle):
		# Skip the data sub-blocks
		blkSize = handle.read(1)
		while len(blkSize) and ord(blkSize) != 0x00:
			handle.seek( handle.tell() + ord(blkSize) )
			blkSize = handle.read(1)
		return len(blkSize)

	warnFlags, frameCount = WARN_NONE, 0 # bitField, integer (unsigned)
	header = fh.read(6)
	if header not in ['GIF87a', 'GIF89a']:
		return ERR_HDR, warnFlags, frameCount, "Bad Header. Are you sure this file is a GIF image?"

	# Skip the screen descriptor (TODO: Validate it)
	fh.seek(fh.tell() + 4)
	fields = fh.read(1)
	fh.seek(fh.tell() + 2)
	
	#Skip the global color table if present
	skipColorTable(fields, fh)
			
	blocktype = fh.read(1)
	while not blocktype == chr(0x3B):
		if   blocktype == '':
			return ERR_EOF, warnFlags, frameCount, "Missing image trailer."
		elif ord(blocktype) == 0x21: # Extension Block (Application, Graphic Control, Plain Text, Comment, etc.)
			fh.seek( fh.tell() + 1 )            # Skip the extension type label
			blkSize = fh.read(1)                # Read in the block size
			fh.seek( fh.tell() + ord(blkSize) ) # Skip the contents

			# Test for the block terminator
			if not skipSubBlocks(fh):
				warnFlags = warnFlags | WARN_BAD_EXT 
			
		elif ord(blocktype) == 0x2C: # Image Block
			frameCount += 1
			fh.seek( fh.tell() + 8 )
			fields = fh.read(1)

			# Skip the local color table if present
			skipColorTable(fields, fh)
			
			fh.seek( fh.tell() + 1 ) # skip the LZW minimum code size.

			# Test for the block terminator
			if not skipSubBlocks(fh): # For example, if it's a zero-length string like EOF would return.
				warnFlags = warnFlags | WARN_BAD_IMG
			
		blocktype = fh.read(1)

	return ERR_NONE, warnFlags, frameCount, "No structural errors detected"

if __name__ == '__main__':
	import sys
	if len(sys.argv) > 1:
		for item in sys.argv[1:]:
			handle = file(item, 'rb')
			results = check_gif(handle)
			warnFlags = (results[1] & WARN_BAD_IMG and 'I' or ' ') + (results[1] & WARN_BAD_EXT and 'X' or ' ')
			print "%s [%s](%s Frames): %s" % (results[3], warnFlags, results[2], item)
		print "\nWarning Flags:"
		print " I = Image Chunk Corruption/Truncation"
		print " X = Extension Chunk Corruption/Truncation"
