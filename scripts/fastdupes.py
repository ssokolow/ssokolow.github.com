#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Find Dupes Fast
By Stephan Sokolow (ssokolow.com)

Inspired by Dave Bolton's dedupe.py (http://davebolton.net/blog/?p=173) and
Reasonable Software's NoClone.

A simple script which identifies duplicate files several orders of magnitude
more quickly than fdupes by using smarter algorithms.

This script supports both comparison by SHA1 hash and, to eliminate the
vanishingly-small but present risk of hash collisions, also supports exact
file comparison.

(Exact comparison does a lot of seeking, so it will be significantly slower
on a traditional hard drive, but may be noticeably faster on a solid-state
drive since it reads files incrementally and can stop as soon as a difference
is encountered.)

Grouping by size and doing a preliminary pass to compare file headers are both
used to significantly reduce the amount of comparison necessary. This also
serves to limit both the memory consumption and the number of open file
handles when doing exact comparisons.

Finally, unlike with fdupes, under no circumstances will the --delete option
allow you to accidentally delete every copy of a file. (No --symlinks option is
supported and this script will not be confused by specifying the same directory
multiple times on the command line or specifying a directory and its parent.)

Note: This file has full Epydoc API documentation.

--snip--

@todo: Add support for saying "If the choice is between files in
    C{/srv/fservroot} and C{/srv/Burned}, automatically delete the ones in
    C{/srv/Burned}"

    Probably via a C{--prefer} command-line switch and a "prefer <path>"
    syntax for dynamically adding preferences part-way through a run.

@todo:
 - Decide what to do having discovered U{https://github.com/sahib/rmlint}
 - Rewrite to put the grouping logic in a single C{groupByKey(paths, keymaker)}
 - The result groups should be sorted by their first entry and the entries
   within each group should be sorted too.
 - As I understand it, C{fnmatch.fnmatch} uses regexes internally and doesn't
   cache them. Given how many times it gets called, I should try using
   C{re.compile} with C{fnmatch.translate} instead.
 - When in hash comparison mode, skip the second comparison for files small
   enough to be fully-compared by the header comparison.
 - Look into the performance effect of checking whether excludes contain
   meta-characters and using simple string matching if they don't.
 - Group files by C{stat().st_ino} to avoid reading from the same inode more
   than once and to allow advanced handling of hardlinks in C{--delete} mode.
    - Offer a switch to automatically hardlink all duplicates found which share
      a common partition.
 - Identify the ideal values for L{CHUNK_SIZE} and L{HEAD_SIZE}... or
   how about dynamically tuning the read increment size based on the number of
   files being compared and possibly the available RAM? (To minimize seeking)
    - C{block_size = min(max_block_size, max_consumption / file_count)}
    - Maybe a 64K maximum block size, 4K minimum block size, and an 8MB max
      consumption? (subordinate to minimum block size when in conflict)
    - Is there such a thing as a disk access profiler I could use with this?
 - Confirm that the byte-by-byte comparison's short-circuit evaluation is
   working properly and efficiently.
 - Look into the performance effects of using multiprocessing to set up one
   worker per physical device... and the feasibility of identifying physical
   devices rather than just partitions.
 - Run this through a memory profiler and look for obvious bloat to trim.
 - Look into possible solutions for pathological cases of thousands of files
   with the same size and same pre-filter results. (File handle exhaustion)
 - Add a mode which caches hashes indexed by C{(path,size,mtime/ctime)} so
   users can trade away a bit of accuracy for a lot more speed.
 - Look into supporting gettext localization.
 - Support displaying duplicated directory trees as single results.
 - Once ready, announce this in a comment at
   U{http://ubuntu.wordpress.com/2005/10/08/find-duplicate-copies-of-files/}
 - Add support for C{\\n} and C{\\x00}-separated stdin file lists.

@todo: Look into C{schweikh3.c}::
   <mauke> feature request: if you could make it output compatible with
   http://www.ioccc.org/1998/schweikh3.hint , that would be sweet
   (http://www.ioccc.org/1998/schweikh3.c)

@todo: Look into C{samefile}::
    <mauke> I don't like the way fdupes works. samefile's interface is superior
    <mauke> it says if you specify a directory twice, it will list files as
            their own duplicates.
    <mauke> wtf was the author thinking?
    <deitarion> mauke: Lazy, I guess. I believe I fixed that in fastdupes.

@todo: Clean up string formatting::
  <mauke> wow, a dynamic format string
  <mauke> "%%%ds: %%s" confused me for a second there :-)
  <mauke> doesn't python know about "%*d"?
  <deitarion> Not sure. I've never heard of it.
  <mauke> er, "%*s"
  <deitarion> The dynamic format string is a trick I first picked up when doing
              string substitution on optparse usage lines where you have to
              escape %prog if you use it.
  <mauke> well, in Perl I'd just do something like:
              my $max = max(map length, keys %DEFAULTS);
              ...
              printf "%*s: %s\\n", $max, $key, $value;
  <mauke> (or in C, but then I'd have to write my own max() and stuff)
  <deitarion> Given that Google doesn't search punctuation, mind explaining
              what %*s does?
  <mauke> see http://perldoc.perl.org/functions/sprintf.html for details, but:
  <mauke> you can use * instead of a hardcoded width (and .* instead of
              precision)
  <mauke> printf will then take an (integer) argument and substitute it
  <mauke> so printf("%*s", 10, "foo") is equivalent to printf("%10s", "foo")
  <deitarion> Hmm. It does support %*s. Another thing to make a TODO note for.
  <mauke> this is more important in C because dynamically generated format
              strings are much more painful there and the compiler can't check
              your args anymore, but it's still nice to have
  http://docs.python.org/library/stdtypes.html#string-formatting

@newfield appname:Application Name

"""


__appname__ = "Find Dupes Fast"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.3.6"
__license__ = "GNU GPL 2.0 or later"

import fnmatch, os, stat, sys

try:
    set() # Initializer shuts PyChecker up about unused
except NameError:
    from sets import Set as set # pylint: disable=W0622

#: Default settings used by C{optparse} and some functions
DEFAULTS = {
          'delete' : False,
         'exclude' : ['*/.svn', '*/.bzr'],
        'min_size' : 25, # Only check files this big or bigger.
}
CHUNK_SIZE = 65536 #: Size for chunked reads from file handles
HEAD_SIZE  = 65536 #: Limit for how many bytes will be read to compare headers

#: Theoretical ideal minimum chunk size
#:
#: According to the hard drive data sheets I examined, the average latency to
#: acquire a specific block (seek time, rotational latency, etc.) ranges from
#: roughly 14ms to 3ms.
#:
#: Assuming that the average uncached, seekless throughput
#: for a modern disk drive ranges from 60MB/s (as Google and C{hdparm} seem to
#: agree on for 7200 RPM drives) and 73MB/s (lower bound for 15K RPM drives
#: according to manufacturer data sheets), then the point where read time
#: overtakes seek time in best-case scenarios for pseudo-parallel reads is at::
#:  73 MB/s / 1000 ms/s * 3.0ms = 0.219MB = 219KB
#:  219KB * (1000/1024 KB/KiB) = 213.8672KiB
#:
#: As such, 216KiB (round up to a multiple of 4KiB) should be a good
#: rule-of-thumb lower bound for chunk sizes. (Actual chunk size must take
#: available RAM into account since, theoretically, a user may use this on a
#: system with tons of dupes of a single file)
#:
#: @todo: Actually use this value.
#: @todo: Gather statistical information on the characteristics of
#: commonly-duplicated files to further tune this.
#: @note: `C{/proc/sys/vm/drop_caches} is probably B{part} of what I'll need to
#:        use to flush caches for cold-start benchmarking.
#:        (If nothing else, I'll still need a way to invalidate the hard
#:        drive's cache)
#:        (Source: https://lwn.net/Articles/562211/ )
IDEAL_MIN_CHUNK_SIZE = 216 * 1024

#{ General Helper Functions

# We need os.lstat so we can skip symlinks, but we want Windows portability too
try:
    _stat = os.lstat
except AttributeError:
    _stat = os.stat

# Note: In my `python -m timeit` tests, the difference between MD5 and SHA1 was
# negligible, so there is no meaningful reason not to take advantage of the
# reduced potential for hash collisions SHA1's greater hash size offers.
try:
    import hashlib
    hasher = hashlib.sha1 # pylint: disable=E1101
except (ImportError, AttributeError):
    # Backwards-compatibility for pre-2.5 Python.
    import sha
    hasher = sha.new

def hashFile(handle, want_hex=False, limit=None, chunk_size=CHUNK_SIZE):
    """Generate an SHA1 hash for a potentially long file.
    Digesting will obey L{CHUNK_SIZE} to conserve memory.

    @param handle: A file-like object or path to hash from.
    @param want_hex: If true, the returned hash will be hex-encoded.
    @param limit: The maximum number of bytes to read (will be rounded up to
        a multiple of C{CHUNK_SIZE})
    @param chunk_size: Size of C{read()} operations in bytes.

    @type want_hex: C{bool}
    @type limit: C{int}
    @type chunk_size: C{int}

    @rtype: C{str}
    @returns: A binary or hex-encoded SHA1 hash.

    @note: It is your responsibility to close any file-like objects you pass in.
    """
    fhash, read = hasher(), 0
    if isinstance(handle, basestring):
        handle = file(handle, 'rb')

    # Chunked digest generation (conserve memory)
    for block in iter(lambda: handle.read(chunk_size), ''):
        fhash.update(block)
        read += chunk_size
        if 0 < limit <= read:
            break

    return want_hex and fhash.hexdigest() or fhash.digest()

#}
#{ Processing Pipeline

def getPaths(roots, ignores=DEFAULTS['exclude']):
    """
    Convert a list of paths containing directories into a list of absolute file
    paths.

    @param roots: Files and folders to walk.
    @param ignores: A list of C{fnmatch.fnmatch} patterns to avoid walking and
        omit from results.

    @returns: List of paths containing only files.
    @rtype: C{list}

    @todo: Try to optimize the ignores matching. Running a regex on every
    filename is a fairly significant percentage of the time taken according to
    the profiler.
    """
    paths, count = [], 0

    # Prepare the ignores list for most efficient use
    # TODO: Check how much of the following should actually be used
    #pats, frag_pats, abs_pats = [], []
    #for pat in ignores:
    #    if '*' in pat or '?' in pat or '[' in pat:
    #        pats.append(re.compile(fnmatch.translate(pat)))
    #    elif pat.startswith(os.sep) or os.altsep and pat.startswith(os.altsep):
    #        abs_pats.append(pat)
    #    else:
    #        frag_pats.append(pat)

    for root in roots:
        # For safety, only use absolute, real paths.
        root = os.path.realpath(root)

        # Handle directly-referenced filenames properly
        # (And override ignores to "do as I mean, not as I say")
        if os.path.isfile(root):
            paths.append(root)
            continue

        for fldr in os.walk(root):
            msg = "\rGathering file paths to compare... (%d files examined)"
            sys.stderr.write(msg % count)

            # Don't even descend into IGNOREd directories.
            for subdir in fldr[1]:
                dirpath = os.path.join(fldr[0], subdir)
                if [x for x in ignores if fnmatch.fnmatch(dirpath, x)]:
                    fldr[1].remove(subdir)

            for filename in fldr[2]:
                filepath = os.path.join(fldr[0], filename)
                if [x for x in ignores if fnmatch.fnmatch(filepath, x)]:
                    continue # Skip IGNOREd files.

                paths.append(filepath)
                count += 1

    msg = "\rFound %s files to be compared for duplication.             \n"
    sys.stderr.write(msg % (len(paths)))
    return paths

def groupBy(groups_in, function, fun_desc='?', keep_uniques=False,
            *args, **kwargs):
    """Subdivide groups of paths according to a function.

    @param groups_in: Groups of path lists.
    @param function: Function which takes a string and list of groups and
        inserts it into an appropriate group.
    @param fun_desc: Human-readable term for what paths are being grouped
        by for use in log messages.
    @param keep_uniques: If false, discard groups with only one member.

    @type paths: C{dict} of iterables
    @type function: C{function(str, dict)}
    @type fun_desc: C{str}
    @type keep_uniques: C{bool}

    @returns: A dict mapping sizes to lists of paths.
    @rtype: C{dict}

    @attention: Grouping functions generally use a C{set} for C{groups} as
        extra protection against accidentally counting a given file twice.
        (Complimentary to C{os.path.realpath()} in L{getPaths})
    """
    groups, count, group_count = {}, 0, len(groups_in)
    for pos, paths in enumerate(groups_in.values()):
        for path in paths:
            msg = "\rSubdividing group %d of %d by %s... (%d files examined)"
            sys.stderr.write(msg % (pos+1, group_count, fun_desc, count))

            function(path, groups, *args, **kwargs)
            count += 1

    if not keep_uniques:
        # Return only the groups with more than one file.
        groups = dict([(x, groups[x]) for x in groups if len(groups[x]) > 1])

    sys.stderr.write("\rFound %s sets of files with identical %s. "
        "(%d files examined)         \n" % (len(groups), fun_desc, count))
    return groups

def sizeGrouper(path, groups, min_size=DEFAULTS['min_size']):
    """Sort a file into a group based on on-disk size.

    @param path: The path to the file to group.
    @param groups: A dict mapping sizes to C{set()}s.
    @param min_size: Files smaller than this size (in bytes) will be ignored.

    @type path: C{str}
    @type groups: C{dict}
    @type min_size: C{int}

    @todo: Rework the calling of stat() to minimize the number of calls. It's a
    fairly significant percentage of the time taken according to the profiler.
    """
    filestat = _stat(path)
    if stat.S_ISLNK(filestat.st_mode):
        return # Skip symlinks.

    if filestat.st_size >= min_size:
        groups.setdefault(filestat.st_size, set()).add(path)

def hashGrouper(path, groups, limit=HEAD_SIZE):
    """Sort a file into a group based on its SHA1 hash.

    @param path: The path to the file to group.
    @param groups: A dict mapping hashes to C{set()}s.
    @param limit: Only this many bytes will be counted in the hash.
        Values which evaluate boolean False indicate no limit.

    @type path: C{str}
    @type groups: C{dict}
    @type limit: C{int}

    """
    headHash = hashFile(path, limit)
    groups.setdefault(headHash, set()).add(path)

#TODO: Rework groupBy and subgroupByContents to unify them.
def subgroupByContents(fileGroups, uniques=False):
    """Further subdivide a list of file groups by content equality.

    Compares block-by-block using parallel reads. Lacks the remote potential of
    hash collisions present with hash comparison... but is heavy on disk seeks.

    See L{compareFiles} for more details.

    @param fileGroups: Any dict with lists of files for keys.
    @param uniques: If false, discard groups with only one member.

    @type fileGroups: C{dict}
    @type uniques: C{bool}

    @returns: A list of lists containing identical files.
    @rtype: C{list}
    """
    """

    """
    dupeGroups, processed = [], 0
    for group in fileGroups.values():
        msg = "\rScanning for real duplicates... %s of %s sets processed"
        sys.stderr.write(msg % (processed, len(fileGroups)))
        # By doing it this way, I minimize the number of file handles open at
        # any given time. (group by group)
        dupeGroups.extend(compareFiles(group))
        processed += 1

    if not uniques:
        results = [x for x in dupeGroups if len(x) > 1]

    msg = "\rFound %s sets of duplicate files. (processed %s potential sets)\n"
    sys.stderr.write(msg % (len(results), len(fileGroups)))

    # Keep the same API as the others.
    return {x:y for x,y in enumerate(results)}

def compareFiles(paths):
    """Byte-for-byte comparison on an arbitrary number of files in parallel.

    This operates by opening all files in parallel and comparing
    chunk-by-chunk. This has the following implications:
        - Reads the same total amount of data as hash comparison.
        - Performs a I{lot} of disk seeks. (Best suited for SSDs)
        - Vulnerable to file handle exhaustion if used on its own.

    @param paths: List of potentially identical files.
    @type paths: iterable

    @returns: List of lists containing identical files.
    @rtype: C{list}

    @todo: Start examining the C{while handles:} block to figure out how to
        minimize thrashing in situations where read-ahead caching is active.
        Compare savings by read-ahead to savings due to eliminating false
        positives as quickly as possible. This is a 2-variable min/max problem.
    """
    handles, results = [], []

    # Silently ignore files we don't have permission to read.
    hList = []
    for path in paths:
        try:
            hList.append((path, open(path, 'rb'), ''))
        except IOError:
            pass #TODO: Verbose-mode output here.
    handles.append(hList)

    while handles:
        # Process more blocks.
        more, done = compareChunks(handles.pop(0))

        # Add the results to the top-level lists.
        handles.extend(more)
        results.extend(done)
    return results

def compareChunks(handles, chunkSize=CHUNK_SIZE):
    """Group a list of file handles based on equality of the next chunk of
    data read from them.

    @param handles: A list of open handles for file-like objects with
        potentially-identical contents.
    @param chunkSize: The amount of data to read from each handle every time
        this function is called.

    @returns: Two lists of lists:
     - One containing more lists to be fed back into this function individually
     - One containing finished groups of duplicate paths. (includes unique
       files as single-file lists)
    @rtype: C{(list, list)}

    @attention: File handles will be automatically-closed when no longer needed.
    @todo: Discard the chunk contents immediately once they're no longer needed.
    """
    chunks = [(path, fh, fh.read(chunkSize)) for path, fh, _ in handles]
    more, done = [], []

    # While there are combinations not yet tried...
    while chunks:
        # Compare the first chunk to all successive chunks
        matches, non_matches = [chunks[0]], []
        for chunk in chunks[1:]:
            if matches[0][2] == chunk[2]:
                matches.append(chunk)
            else:
                non_matches.append(chunk)
        # Check for EOF or obviously unique files
        if len(matches) == 1 or matches[0][2] == "":
            for x in matches:
                x[1].close()
            done.append([x[0] for x in matches])
        else:
            more.append(matches)
        chunks = non_matches

    return more, done

#}
#{ User Interface

def pruneUI(dupeList, mainPos=1, mainLen=1):
    """Display a list of files and prompt for ones to be kept.

    The user may enter "all" or one or more numbers separated by spaces and/or
    commas.

    @note: It is impossible to accidentally choose to keep none of the
        displayed files.

    @param dupeList: A list duplicate file paths
    @param mainPos: Used to display "set X of Y"
    @param mainLen: Used to display "set X of Y"
    @type dupeList: C{list}
    @type mainPos: C{int}
    @type mainLen: C{int}

    @returns: A list of files to be deleted.
    @rtype: C{list}
    """
    dupeList = sorted(dupeList)
    print
    for pos, val in enumerate(dupeList):
        print "%d) %s" % (pos+1, val)
    while True:
        choice = raw_input("[%s/%s] Keepers: " % (mainPos, mainLen)).strip()
        if not choice:
            print "You must specify at least one file to keep."
            continue
        elif choice.lower() == 'all':
            return []
        try:
            out = [int(x)-1 for x in choice.replace(',',' ').split()]
            return [val for pos, val in enumerate(dupeList) if not pos in out]
        except ValueError:
            print("Invalid choice. Please enter a space/comma-separated list"
                  "of numbers or 'all'.")

#}

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options] <folder path> ...",
            version="%s v%s" % (__appname__, __version__))
    parser.add_option('-D', '--defaults', action="store_true", dest="defaults",
        default=False, help="Display the default values for options which take"
        " arguments and then exit.")
    parser.add_option('-d', '--delete',  action="store_true", dest="delete",
        help="Prompt the user for files to preserve and delete all others.")
    parser.add_option('-E', '--exact', action="store_true", dest="exact",
        default=False, help="There is a vanishingly small chance of false"
        " positives when comparing files using sizes and hashes. This option"
        " enables exact comparison. However, exact comparison requires a lot"
        " of disk seeks, so, on traditional moving-platter media, this trades"
        " a LOT of performance for a very tiny amount of safety most people"
        " don't need.")
    parser.add_option('-e', '--exclude', action="append", dest="exclude",
        metavar="PAT", help="Specify a globbing pattern to be"
        " added to the internal blacklist. This option can be used multiple"
        " times. Provide a dash (-) as your first exclude to override the"
        " pre-programmed defaults.")
    parser.add_option('--min-size', action="store", type="int",
        dest="min_size", metavar="X", help="Specify a non-default minimum size"
        ". Files below this size (default: %s bytes) will be ignored."
        "" % DEFAULTS['min_size'])
    #XXX: Should I add --verbose and/or --quiet?
    parser.set_defaults(**DEFAULTS) # pylint: disable=W0142

    opts, args = parser.parse_args()

    if '-' in opts.exclude:
        opts.exclude = opts.exclude[opts.exclude.index('-') + 1:]
    opts.exclude = [x.rstrip(os.sep + (os.altsep or '')) for x in opts.exclude]
    # This line is required to make it match directories

    if opts.defaults:
        formatStr = "%%%ds: %%s" % max([len(x) for x in DEFAULTS])
        for key in DEFAULTS:
            value = DEFAULTS[key]
            if isinstance(value, (list, set)):
                value = ', '.join(value)
            print formatStr % (key, value)
        sys.exit()

    groups = {'': getPaths(args, opts.exclude)}
    groups = groupBy(groups, sizeGrouper, 'sizes', min_size=opts.min_size)

    # This serves one of two purposes depending on run-mode:
    # - Minimize the number of files checked by full-content comparison (hash)
    # - Minimize the chances of file handle exhaustion and limit seeking (exact)
    groups = groupBy(groups, hashGrouper, 'header hashes', limit=HEAD_SIZE)

    if opts.exact:
        groups = subgroupByContents(groups)
    else:
        groups = groupBy(groups, hashGrouper, 'hashes')

    if opts.delete:
        for pos, val in enumerate(groups):
            #TODO: Add a secondary check for symlinks for safety.
            pruneList = pruneUI(val, pos+1, len(groups))
            for path in pruneList:
                os.remove(path)
    else:
        for dupeSet in groups.values():
            for filename in dupeSet:
                print filename
            print
