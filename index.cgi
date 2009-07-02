#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A single-file Python CGI script for effortless sharing of other single-file
scripts. If you're viewing a "Useful Hacks" list on my website, this is the
code behind it.

Simply put your desired description into each file's docstring (for shell
scripts, it takes every commented line starting with the shabang and ending
with the first non-comment line) and drop them into a folder along with
this script. Currently supports Bourne-compatible shell scripts and Python
scripts. Other languages under consideration.

Non-obvious Features:
- Hyperlinks URLs and obfuscates e-mail addresses in script descriptions.
- Configurable license name hyperlinking

Warnings:
- The HTML templating is a quick hackjob. I'm not kidding.
- Don't forget to change the <title> and remove my Google Analytics footer.

TODO: Switch to a proper templating solution?
"""

__appname__ = "Lazybones Script Lister"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.3"
__license__ = "GNU GPL 2.0 or later"

import cgi, os, parser, re, time, token, urllib

DEFAULT_LICENSE = "GNU GPL 2.0 or newer"

LICENSES = {
        re.compile("(^|\b)((GNU )?GPL v?2(\.0)?)", re.IGNORECASE) : "http://www.gnu.org/licenses/gpl-2.0.html"
        }

PAGE_HEADER = """Content-Type: text/html; charset=utf-8

<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN"
   "http://www.w3.org/TR/html4/strict.dtd">
<html>
    <head>
        <title>Useful Hacks @ ssokolow.com</title>

        <style type="text/css">
            h2 {
                border-bottom: 2px solid black;
                padding-left: 1ex;
            }
            a { text-decoration: none; }
            a:hover { text-decoration: underline; }

            .docstring {
                margin-left: 1em;
                margin-right: 1em;
                border: 1px solid gray;
                color: black;
                background-color: #eeeeee;
                padding: 1em;
                -moz-border-radius: 1em;
                width: 50em;
            }

            .attr_list {
                list-style-type: none;
                padding-left: 1em;
            }
            .attr_list .key { font-weight: bold; }

            .menu {
                position: fixed;
                color: black;
                background-color: white;
                border: 1px solid black;
                padding: 0 1ex 1ex 1ex;
                top: 1em;
                right: 1em;
                width: 15em;
            }
            .menu .backlink {
                display: block;
                text-align: center;
            }
            .menu h2 {
                padding-left: 0;
                text-align: center;
            }


            div.header { margin-right: 20em; }
            div.footer {
                border-top: 2px solid black;
                padding: 1ex;
                text-align: center;
            }
        </style>

    </head>
    <body>
        <div class="header">
            <h1>Useful Hacks</h1>
            <p>This page lists scripts I quickly hacked up to solve a problem but
                haven't had time to clean up for general use. Feel free to use
                them if you like. Unless otherwise stated, they're licensed under
                the GNU GPL version 2 or later.</p>
        </div>
"""

PAGE_FOOTER = """
<div class='footer'>
    """ + time.strftime("This page generated at %Y-%m-%d %H:%M UTC", time.gmtime()) + """
</div>
<script type="text/javascript">
var gaJsHost = (("https:" == document.location.protocol) ? "https://ssl." : "http://www.");
document.write(unescape("%3Cscript src='" + gaJsHost + "google-analytics.com/ga.js' type='text/javascript'%3E%3C/script%3E"));
</script>
<script type="text/javascript">
var pageTracker = _gat._getTracker("UA-2187569-1");
pageTracker._initData();
pageTracker._trackPageview();
</script>
    </body>
</html>"""

bad_anchor_char_re   = re.compile('[^A-Za-z0-9-_:.]+')
hyperlinkable_url_re = re.compile(r"""((?:ht|f)tps?://[^\s()]+(?:\([^\s()]+\))*[^\s()]*)""", re.IGNORECASE | re.UNICODE)

_bc = r"""!@#$%^&*()=+{}[\]|\;:'"/?>,<\s"""
email_address_re     = re.compile(r"""(?P<email>[^%s]+@[^%s]+\.[^%s]*[^.%s])""" % (_bc, _bc, _bc, _bc), re.UNICODE)
del _bc

class ScriptEntry(object):
    _metadata = {
        'name'        : '',
        'filepath'    : '',
        'filename'    : '',
        'filesize'    : 0,
        'filetime'    : 0,
        'language'    : '',
        'description' : '',
        'anchor'      : '',
        'license'     : DEFAULT_LICENSE,
        'version'     : '',
    }

    shabang_re = None
    license_re = None
    extensions = []

    def __cmp__(self, other):
        """Make ScriptEntry objects case-insensitive sortable by name."""
        return cmp(self.metadata['name'].lower(), other.metadata['name'].lower())

    def __init__(self, filename):
        self.metadata = self._metadata.copy()

        tmp = os.stat(filename)

        # Store all the metadata that isn't format-specific.
        _ = self.metadata
        _['filepath'] = os.path.normpath(filename)
        _['filename'] = os.path.basename(self.metadata['filepath'])
        _['filesize'] = tmp.st_size
        _['filetime'] = tmp.st_mtime

        # Construct a hyperlinkable anchor from the filename
        _['anchor'] = bad_anchor_char_re.sub('_',_['filename']).lower()
        if not _['anchor'][0].isalpha():
            _['anchor'] = 'a' + _['anchor']
        #TODO: Fix this to avoid the possibility of duplicate anchors.

        # Make sure that the filename will be used as a fallback program name.
        _['name'] = _['filename']

        # Actually extract the metadata.
        self._do_init()

        # Allow controlled truncation of module docstrings.
        if '\n--clip--\n' in _['description']:
            _['description'] = _['description'].split('\n--clip--\n',1)[0] + '\n[...]'

        # Add various pretty-printed and escaped values to the metadata dict.
        _.update({
            'fname_q': urllib.quote_plus(self.metadata['filename']),
            'fsize_p':formatFileSize(self.metadata['filesize']),
            'desc_e': self._xml_escape(self.metadata['description']),
            'mtime': time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(self.metadata['filetime']))
        })

        # Hyperlink all the URLs in the description.
        _['desc_e'] = hyperlinkable_url_re.sub(r'<a href="\1">\1</a>', _['desc_e'])

        # Add some spam protection to any e-mail addresses
        _['desc_e'] = email_address_re.sub(spamProtectEmail, _['desc_e'])

        # Hyperlink any licenses we can.
        _['license_h'] = _['license']
        for regex in LICENSES:
            if regex.search(_['license']):
                _['license_h'] = regex.sub(r'<a href="%s">\2</a>' % LICENSES[regex], _['license'])

    def _do_init(self):
        raise NotImplementedError("Cannot instantiate abstract class")

    def _xml_escape(self, instr):
        return instr.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

    def render(self):
        output = """<h2 id="%(anchor)s">
                <a href='?get=%(fname_q)s'>%(name)s</a>
            </h2>
            <ul class="attr_list">
                <li><span class="key">Size:</span> %(fsize_p)s</li>""" % self.metadata
        if self.metadata['version']:
            output += '\n<li><span class="key">Version:</span> %(version)s</li>\n' % self.metadata
        output += """<li><span class="key">License:</span> %(license_h)s</li>
                <li><span class="key">Language:</span> %(language)s</li>
                <li><span class="key">Last Modified:</span> %(mtime)s</li>
            </ul>
            <pre class='docstring'>%(desc_e)s</pre>""" % self.metadata
        return output

class PythonScriptEntry(ScriptEntry):
    shabang_re = re.compile('^#!(/usr(/local)?)?/bin/(env )?python')
    extensions = ['.py']

    _variable_re = r"""^%s\s*=\s*(?P<delim>'{1,3}|\"{1,3})(?P<value>.+?)(?P=delim)\s*$"""
    _metadata_regexes = {
            'license' : re.compile(_variable_re % '__license__', re.MULTILINE),
               'name' : re.compile(_variable_re % '__appname__', re.MULTILINE),
            'version' : re.compile(_variable_re % '__version__', re.MULTILINE)
            }

    def _do_init(self):
        _ = self.metadata
        _['language'] = 'Python'

        # Load the file and extract all metadata but the description.
        filecontents = open(_['filepath'], 'rU').read()
        for key in self._metadata_regexes:
            match_obj = self._metadata_regexes[key].search(filecontents)
            if match_obj:
                self.metadata[key] = match_obj.group('value')

        # Parse out the module docstring as the description.
        try:
            _['description'] = self._get_docstring(filecontents)
        except:
            _['description'] = "ERROR: Unable to parse file."

    def _get_docstring(self, tup):
        """
        Module docstring extractor.
        Written because Demo/parser/example.py DOESN'T WORK.
        """
        if isinstance(tup, basestring):
            tup = parser.suite(tup).totuple()

        if tup[0] == token.STRING:
            return tup[1]
        for value in tup:
            if isinstance(value, tuple):
                val = self._get_docstring(value)
                if val:
                    return val

class ShellScriptEntry(ScriptEntry):
    shabang_re = re.compile('^#!(/usr(/local)?)?/bin/(env )?(ba|k)?sh$')
    extensions = ['.sh']

    _license_re = re.compile(r"""^#\s*(Licensed|Released) under (the|a) (?P<license>.+?)(\slicense)?\.?\s*$""", re.M | re.I)

    def _do_init(self):
        _ = self.metadata
        _['language'] = 'Bourne Shell Script'

        # Extract the comment block header as the description if present
        lines = []
        for line in file(_['filepath']):
            line = line.strip()
            if line.startswith('#'):
                lines.append(line)
            else:
                break
        _['description'] = '\n'.join(lines)

        # Extract the license info if present
        match_obj = self._license_re.search(_['description'])
        if match_obj:
            self.metadata['license'] = match_obj.group('license')

entryClasses = [PythonScriptEntry, ShellScriptEntry]

def spamProtectEmail(match_obj):
    """Use this as the replacement in a regex substitution with email_address_re
    to provide some degree of spam protection for e-mail addresses in docstrings

    XXX: Should I add some randomness to the obfuscation approach?"""
    maps = {'@' : ' at ', '.' : ' dot '}

    email = match_obj.group(0)
    for char in maps:
        email = email.replace(char, maps[char])

    return email

def formatFileSize(size,unit='',precision=0):
    """Take a size in bits or bytes and return it all prettied
    up and rounded to whichever unit gives the smallest number.

    A fixed unit can be specified. Possible units are B, KB,
    MB, GB, TB, and PB so far. Case-insensitive.

    Works on both negative and positive numbers. In the event
    that the given value is in bits, the user will have to
    use result = result[:-1] + 'b' to make it appear correct.

    Will calculate using integers unless precision is != 0.
    Will display using integers unless precision is > 0."""

    # Each unit's position in the list is crucial.
    # units[2] = 'MB' and size / 1024**2 = size in MB
    units = ['bytes','KiB','MiB','GiB','TiB','PiB','EiB','ZiB','YiB']

    if precision: size = float(size)
    # Did the calling function specify a valid unit of measurement?
    if unit and unit.upper() in units:         # If so, find the unit index by searching.
        unit_idx = units.index(unit)
        size /= (1024**unit_idx)
    else:                                      # If not, find the unit index by iteration.
        unit_idx = 0
        while abs(size) > 1024 and unit_idx < (len(units) - 1):
            size /= 1024
            unit_idx += 1

    return '%.*f %s' % (precision,size,units[unit_idx])

def list_content():
    """Generate an HTML listing of the available files, complete with metadata"""
    import glob

    scripts = []
    for name in os.listdir('.'):
        ext = os.path.splitext(name)[1]
        for ec in entryClasses:
            if ext in ec.extensions:
                scripts.append(ec(name))
                continue

            lineOne = file(name).readline()
            if ec.shabang_re.match(lineOne):
                scripts.append(ec(name))
    scripts.sort()

    print PAGE_HEADER
    print "<div class='menu'><h2>Table of Contents</h2><ol>"
    for entry in scripts:
        print "<li><a href='#%s'>%s</a></li>" % (entry.metadata['anchor'], entry.metadata['name'])
    print "</ol><hr><a href='/' class='backlink'>Back to Main Site</a></div>"
    for entry in scripts:
        print entry.render()
    print PAGE_FOOTER

if __name__ == '__main__':
    form = cgi.FieldStorage()
    if not form.has_key("get"):
        list_content()
    else:
        fname = os.path.normpath(form['get'].value)
        if not os.path.abspath(fname).startswith(os.getcwd()) or not os.path.isfile(fname):
            print PAGE_HEADER
            print "<p>Unfortunately, you have requested an invalid file. Please <a href='?'>try again</a>.</p>"
            print PAGE_FOOTER
        else:
            print "Content-Type: text/plain"
            print
            print file(form['get'].value).read()

