#!/usr/bin/env python
"""
A script for swapping the audio-track byte order in cdrdao .BIN files so that a
.CUE file generated by toc2cue can be mounted by DOSBox or CDEmu.

2016-03-03: Since I've been meaning to fix this since 2009 and it was
            embarassing, I rewrote it just enough that it isn't doing a syscall
            for every two bytes.

TODO:
- Rewrite in Rust and optimize.
"""

__license__ = "GNU GPL 2.0 or newer"

import locale, os, shlex, sys
locale.setlocale(locale.LC_ALL, '')

CHUNK_SIZE = 256 * 1024

def time_to_frames(timecode):
	mins, secs, frames = [int(x) for x in timecode.split(':')]
	return 75 * (mins * 60 + secs) + frames

def get_extents(fh):
	already_file, offset, track_type, tracks = False, None, None, []

	for line in fh:
		line = line.strip()
		if line.startswith('FILE'):
			if already_file:
				raise Exception("Given cuesheet contains references to multiple files.")
			else:
				binfile, mode = shlex.split(line)[1:3]
				if mode != 'BINARY':
					raise Exception("Given cuesheet does not reference a BINARY source file.")
		elif line.startswith('TRACK'):
			previous_type = track_type
			track_type = line.split()[2]
		elif line.startswith('INDEX'):
			previous_offset = offset
			offset = time_to_frames(line.split()[2]) * 2352
			if previous_type == 'AUDIO':
				tracks.append((previous_offset, offset))
				# Build a list of start-stop pairs for audio tracks

	# Make sure we don't omit the final track
	if track_type == 'AUDIO':
		tracks.append((offset, os.stat(binfile).st_size))

	# Simplify the problem by combining extents (In all sane cases, will produce a single giant extent)
	temp, start, stop = [], tracks[0][0], tracks[0][1]
	for pos in range(0, len(tracks) - 1):
		if tracks[pos][1] == tracks[pos+1][0]:
			stop = tracks[pos+1][1]
		else:
			temp.append((start, stop))
			start = tracks[pos+1][0]
			stop = tracks[pos+1][1]
	temp.append((start, stop))
	tracks = temp

	return binfile, tracks

if __name__ == '__main__':
	if len(sys.argv) != 3:
		print "Usage: %s <cue file> <target bin file>" % sys.argv[0]
		sys.exit(1)

	binfile, tracks = get_extents(file(sys.argv[1]))

	if os.path.realpath(binfile) == os.path.realpath(sys.argv[2]):
		print "Please specify a target filename different from the source filename."
		sys.exit(2)

	# Reverse the endianness on the audio tracks.
	infile, outfile = file(binfile, 'rb'), file(sys.argv[2], 'wb')
	while infile.tell() < tracks[0][0]:
		temp = infile.read(min(CHUNK_SIZE, tracks[0][0] - infile.tell()))
		outfile.write(temp)
	if infile.tell() > tracks[0][0]:
		raise Exception("Overshot our mark!")
	for start, stop in tracks:
		offset = infile.tell()
		while offset < stop:
			sys.stdout.write('\rProcessing offset %s' %
				 locale.format('%d', offset, grouping=True))
			amount = min(CHUNK_SIZE, stop - infile.tell())
			if amount % 2 != 0:
				raise Exception("Remaining byte count not divisible by 2")

			chunk = infile.read(amount)
			for chunk_offset in range(0, amount, 2):
				outfile.write(chunk[chunk_offset + 1] + chunk[chunk_offset])
			offset = infile.tell()
		sys.stdout.write('\rDone.                                   \n')

	infile.close(); outfile.close()
