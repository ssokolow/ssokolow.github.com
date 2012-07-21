#!/bin/bash
# enc_ogg+flac.sh
# By: Stephan Sokolow
#
# A wrapper script to allow KAudioCreator to encode to both Ogg Vorbis and FLAC
# in one run Also normalizes the input file to avoid the need to do so twice
# later on.
#
# Licensed under the GNU GPL 2 or later.

if [ $# -le 1 ]; then
	echo "Usage: $0 <infile.wav> <outfile.flac> [<title>] [<artist>] [<album>] [<year>] [<number>] [<genre>]"
	echo "KAudioCreator Command Line: $0 %f %o %{title} %{artist} %{albumtitle} %{year} %{number} %{genre}"
	echo "Always use the .flac extension on the outfile so that the script can substitute the correct extension for the .ogg step"
	exit 1
fi

if `which normalize-audio` >/dev/null; then
    normalize-audio -q "$1"
elif `which normalize` >/dev/null; then
    normalize -q "$1"
fi

OUT=$(sed 's@.flac$@.ogg@' <<< "$2")
oggenc -q 5 -o "$OUT" --title "$3" --artist "$4" --album "$5" --date "$6" --tracknum "$7" --genre "$8" "$1"

flac --best -o "$2" --tag=Title="$3" --tag=Artist="$4" --tag=Album="$5" --tag=Date="$6" --tag=Tracknumber="$7" --tag=Genre="$8" "$1"
