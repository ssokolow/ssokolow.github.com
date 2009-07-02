#!/usr/bin/env python
"""upd_hosts.py
Automatically generates /etc/hosts from /etc/hosts.local and the MVPS
ad-blocking hosts list.

Instructions:
Put this file in /etc/cron.monthly and chmod it executable.

Edit the ADHOST_SUFFIX_WHITELIST variable if you want. (Default is to allow only
Project Wonderful because I respect them and they don't serve up flash ads)

TODO:
- Use If-Modified-Since and ETags on the MVPS file so I can safely run this
  more often. (Perhaps also use the ZIP download to save bandwidth?)
- Add a mode which doesn't require the local hosts file to be moved to
  /etc/hosts.local
"""

MVPS_URL = 'http://www.mvps.org/winhelp2002/hosts.txt'
LOCAL_HOSTS = '/etc/hosts.local'
ADHOST_SUFFIX_WHITELIST = ['.projectwonderful.com']

import os, sys, urllib2

def checkStart(line):
    """Only pass lines which are comments or 127.0.0.1 lines to ensure that
    downloaded hosts lists can't be hijacked for DNS-based phishing.

    Strip out lines which would block hosts in ADHOST_SUFFIX_WHITELIST."""
    line = line.split('#',1)[0].strip() # Compare only the relevant portion.

    for suffix in ADHOST_SUFFIX_WHITELIST:
        if line.endswith(suffix.strip()):
            return False # Don't block whitelisted servers

	for prefix in ('127.0.0.1 ', '127.0.0.1\t', '#'):
		if not line or line.strip().startswith(prefix):
			return True # Allow 127.0.0.1 lines, comments, and blank lines.
	return False # Block everything else.

# Retrieve the MVPS hosts file and play it safe
# by filtering out any non-127.0.0.1, non-comment lines.
adhosts_raw = urllib2.urlopen(MVPS_URL).read().strip().replace('\r','').split('\n')
adhosts = [x for x in adhosts_raw if checkStart(x)]

# Load the local hosts file from /etc/hosts.local
if os.path.exists(LOCAL_HOSTS):
	localhosts = file(LOCAL_HOSTS,'rU').read().strip().split('\n')
else:
	localhosts = []

warning = ["# WARNING: This file was auto-generated.",
"Please edit /etc/hosts.local and run %s instead" % os.path.split(sys.argv[0])[1]]

# Write the new stuff to /etc/hosts
file('/etc/hosts','w').write('\n'.join(warning + [''] + localhosts + [''] + adhosts))
