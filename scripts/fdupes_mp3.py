#!/usr/bin/env python
"""
A crude script for identifying audio files that generate duplicate waveforms

Originally written as an experiment in identifying files that differ only in
metadata. Supports anything sox does.

It's CPU-bound, but because of sparse documentation on the MP3 format, it's
the best I can do for now.

Probably best to use FDMF (http://w140.com/audio/) with some stricter-than-
default thresholds until I find the time to rewrite this to be I/O-bound.

prints duplicates to stdout (one per-line) with groups of duplicates separated
by empty lines. Status messages are sent to stderr.

Warning: Seems to get stuck on .mpg files.

Requires: sox
"""

import os, subprocess, sys

try:
  import hashlib
  def getHasher(): return hashlib.sha1()
except ImportError:
  import sha
  def getHasher(): return sha.new()

def readChunks(fd, chunksize=4096):
  while True:
    chunk = fd.read(chunksize)
    if chunk: yield chunk
    else: break

P_op, PIPE = subprocess.Popen, subprocess.PIPE

def getHash(filepath):
  sys.stderr.write("Checking %s\n" % filepath)

  # Get the file's SHA1 hash.
  hasher = getHasher()
  for chunk in readChunks(P_op(['sox', filepath,'-t','wav','-'], stdout=PIPE, stderr=file('/dev/null','w')).stdout):
    hasher.update(chunk)
  sha1sum = hasher.hexdigest()

  return sha1sum

def getHashes(roots):
  sum_map = {}
  if isinstance(roots, basestring):
    roots = [roots]

  for root in roots:
    if os.path.isfile(root):
      sha1sum = getHash(root)

      if sum_map.has_key(sha1sum):
        sum_map[sha1sum].append(root)
      else:
        sum_map[sha1sum] = [root]
    else:
      for fldr in os.walk(root):
        for filename in fldr[2]:
          filepath = os.path.join(fldr[0],filename)
          sha1sum = getHash(filepath)

          if sum_map.has_key(sha1sum):
            sum_map[sha1sum].append(filepath)
          else:
            sum_map[sha1sum] = [filepath]
  return sum_map

if __name__ == '__main__':
  if len(sys.argv) < 2:
    roots = ['.']
  else:
    roots = sys.argv[1:]

  dup_map = getHashes(roots)
  for dupset in [dup_map[x] for x in dup_map if len(dup_map[x]) > 1]:
    print
    for line in dupset:
      print line

