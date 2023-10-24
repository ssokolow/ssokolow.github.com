#!/usr/bin/env python3
"""upd_hosts.py
Automatically generates /etc/hosts from /etc/hosts.local and the MVPS
ad-blocking hosts list.

Instructions:
Put this file in /etc/cron.monthly and chmod it executable.

Edit the ADHOST_SUFFIX_WHITELIST variable if you want. (Default is to allow
only Project Wonderful because I respect them and they don't serve flash ads)

TODO:
- Use If-Modified-Since and ETags on the MVPS file so I can safely run this
  more often. (Perhaps also use the ZIP download to save bandwidth?)
- Add a mode which doesn't require the local hosts file to be moved to
  /etc/hosts.local
"""

MVPS_URL = 'http://winhelp2002.mvps.org/hosts.txt'
LOCAL_HOSTS = '/etc/hosts.local'
TARGET_HOSTS = '/etc/hosts'
ADHOST_SUFFIX_WHITELIST = [b'.projectwonderful.com', b'piwik.org']

import os, sys, urllib.request, urllib.error, urllib.parse  # NOQA: E401,E402


def checkStart(line):
    """Only pass lines which are comments or 127.0.0.1 lines to ensure that
    downloaded hosts lists can't be hijacked for DNS-based phishing.

    Strip out lines which would block hosts in ADHOST_SUFFIX_WHITELIST."""
    line = line.split(b'#', 1)[0].strip()  # Compare only the relevant portion.

    for suffix in ADHOST_SUFFIX_WHITELIST:
        if line.endswith(suffix.strip()):
            return False  # Don't block whitelisted servers

    for prefix in (b'#', b'127.0.0.1 ', b'127.0.0.1\t',
            b'0.0.0.0 ', b'0.0.0.0\t'):
        if not line or line.strip().startswith(prefix):
            return True  # Allow 127.0.0.1/0.0.0.0 lines, comments, and blanks.
    return False  # Block everything else.


if os.geteuid() == 0:
    # Retrieve the MVPS hosts file and play it safe
    # by filtering out any non-127.0.0.1, non-comment lines.
    adhosts_raw = urllib.request.urlopen(MVPS_URL).read().strip()
    adhosts_raw = adhosts_raw.replace(b'\r', b'').split(b'\n')
    adhosts = [x for x in adhosts_raw if checkStart(x)]

    # integrate local definitions if this is the first time we're being run
    if os.path.exists(TARGET_HOSTS) and not os.path.exists(LOCAL_HOSTS):
        os.rename(TARGET_HOSTS, LOCAL_HOSTS)

    # Load the local hosts file from /etc/hosts.local
    if os.path.exists(LOCAL_HOSTS):
        localhosts = open(LOCAL_HOSTS, 'rb').read().strip().split(b'\n')
    else:
        localhosts = []

    warning = [b"# WARNING: This file was auto-generated.",
    b"# Please edit /etc/hosts.local and run "
    b"%s instead" % os.path.split(sys.argv[0])[1].encode('utf8')]

    output = b'\n'.join(warning + [b''] + localhosts + [b''] + adhosts)

    # Write the new stuff to /etc/hosts
    open(TARGET_HOSTS, 'wb').write(output)
else:
    print("Re-calling via sudo to gain root privileges...")
    os.execvp('sudo', ['sudo', str(__file__)])
