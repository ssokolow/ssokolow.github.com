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
- Don't forget to remove the template bits specific to my site.

TODO:
- Switch to a proper templating solution? (No longer a single-file script)
- Add caching eventually (current run time for my site, 0.1 seconds)
- Add a 5px inset border and subtle "rounded CRT glare" gradients to <pre>
"""

__appname__ = "Lazybones Script Lister"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.3.1"
__license__ = "GNU GPL 2.0 or later"

import cgi, os, parser, re, time, token, urllib
from xml.sax.saxutils import escape as xml_escape

DEFAULT_LICENSE = "GNU GPL 2.0 or newer"

LICENSES = {
        re.compile("(^|\b)((GNU )?(A|Affero )(General Public License|GPL)[ ]?v?3(\.0)?)", re.IGNORECASE): "http://www.gnu.org/licenses/agpl-3.0.html",
        re.compile("(^|\b)((GNU )?(General Public License|GPL)[ ]?v?2(\.0)?)", re.IGNORECASE): "http://www.gnu.org/licenses/gpl-2.0.html",
        re.compile("(^|\b)((GNU )?(General Public License|GPL)[ ]?v?3(\.0)?)", re.IGNORECASE): "http://www.gnu.org/licenses/gpl-3.0.html",
        re.compile("(^|\b)((GNU )?(L|Lesser |Library )(General Public License|GPL)[ ]?v?2\.1)", re.IGNORECASE): "http://www.gnu.org/licenses/lgpl-2.1.html",
        re.compile("(^|\b)((GNU )?(L|Lesser |Library )(General Public License|GPL)[ ]?v?3(\.0)?)", re.IGNORECASE): "http://www.gnu.org/licenses/lgpl-3.0.html",
        re.compile("(^|\b)((Mozilla Public License|MPL)[ ]?v?1\.1)", re.IGNORECASE): "https://www.mozilla.org/MPL/1.1/",
        re.compile("(^|\b)((Mozilla Public License|MPL)[ ]?v?2(\.0)?)", re.IGNORECASE): "https://www.mozilla.org/MPL/2.0/",
        re.compile("(^|\b)(Apache (License )?v?2(\.0)?)", re.IGNORECASE): "http://www.opensource.org/licenses/apache2.0.php",
        re.compile("(^|\b)(Artistic (License )?v?2(\.0)?)", re.IGNORECASE): "http://www.perlfoundation.org/artistic_license_2_0",
        re.compile("(^|\b)(PSF (License )?(\d\.\d)?)", re.IGNORECASE): "http://docs.python.org/license.html",
        re.compile("(^|\b)((Old|Original|4-clause)[ ]?BSD( License)?)", re.IGNORECASE): "https://en.wikipedia.org/wiki/BSD_licenses#4-clause_license_.28original_.22BSD_License.22.29",
        re.compile("(^|\b)((New|Modified|3-clause)[ ]?BSD( License)?)", re.IGNORECASE): "http://www.opensource.org/licenses/BSD-3-Clause",
        re.compile("(^|\b)((2-clause |Simplified |Free)BSD( License)?)", re.IGNORECASE): "http://www.opensource.org/licenses/BSD-2-Clause",
        re.compile("(^|\b)((MIT|X11)( License)?)", re.IGNORECASE): "http://www.opensource.org/licenses/MIT",
        re.compile("(^|\b)((Eclipse Public License|EPL)[ ]?v?1?(\.0)?)", re.IGNORECASE): "http://www.eclipse.org/legal/epl-v10.html"
}

HTACCESS = """
Options -ExecCGI
SetHandler default-handler
DirectoryIndex index.html
"""

PAGE_HEADER = """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN"
   "http://www.w3.org/TR/html4/strict.dtd">
<html>
    <head>
        <title>Useful Hacks @ ssokolow.com</title>

        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href='http://fonts.googleapis.com/css?family=Play:400,700' rel='stylesheet' type='text/css'>
        <style type="text/css">
            body { font-family: sans-serif; }
            p { margin: 1ex; }

            h1, .menu h2, .menu .backlink, h2 .filename { font-family: 'Play', sans-serif; }
            h2 .filename { font-family: 'Play', "DejaVu Sans Mono", "Liberation Mono", "Andale Mono", "Droid Sans Mono", monospace; }

            h2 {
                border-bottom: 2px solid black;
                margin-left: 0.5ex;
                padding-left: 0.3ex;
            }
            a:link {
                text-decoration: none;
                color: #0000EE;
            }
            a:visited { color: #800080; }
            a:hover { text-decoration: underline; }
            a:active { color: #e00; }

            .entry h2 { font-size: 2.2ex; }
            .entry { padding-bottom: 1ex; }

            pre, .generated, .attr_list, p .filename, .menu .filename {
                font-family: "DejaVu Sans Mono", "Liberation Mono", "Andale Mono", "Droid Sans Mono", monospace;
                font-size: 80% !important;
            }

            .to_projects {
                font-size: 60%;
                vertical-align: middle;
            }

            pre {
                margin-left: 1em;
                margin-right: 1em;
                box-shadow: 2px 3px 5px black inset, 2px 2px 2px #888;
                color: #0E0;
                background-color: #000;
                padding: 1em;
                border-radius: 1em;
                -moz-border-radius: 1em;
                -webkit-border-radius: 1em;
                max-width: 50em;
                white-space: pre-wrap;
                clear: right;
                overflow-x: auto;
            }
            pre a, pre a:visited {
                color: #0F0;
                font-weight: bold;
                text-decoration: underline;
            }
            pre a:visited { font-style: italic; }

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

            @media (max-width: 965px) {
                .menu {
                    position: static;
                    float: right;
                }
            }

            div.header { margin-right: 20em; }
            div.footer {
                border-top: 2px solid black;
                padding: 1ex;
                text-align: center;
            }

            .info, .alert {
                padding: 1ex;
                box-shadow: 2px 2px 1px #ddd;
                display: inline-block;
            }
            .info {
                background-color: #ffa;
            }
            .alert {
                background-color: #fdd;
            }
        </style>

    </head>
    <body>
"""

BODY_HEADER = """
        <div class="header">
          <h1>Useful Hacks <span class="to_projects">[<a rel="me"
            href="http://github.com/ssokolow">Projects</a>]</span></h1>
          <p>This page lists scripts I quickly hacked up to solve a problem but
                haven't had time to clean up for general use. Feel free to use
                them if you like.</p>
            <p id="quicktile.py" class="alert"><strong>Note:</strong>
                <span class="filename">quicktile.py</span> is now available as
                <a class="filename"
                href="http://github.com/ssokolow/quicktile/tree/master"
                >ssokolow/quicktile</a> on GitHub.
            </p>
            <p id="fastdupes.py" class="alert"><strong>Note:</strong>
                Find Dupes Fast (A.K.A.
                <span class="filename">fastdupes.py</span>)
                is now available as
                <a class="filename"
                href="http://github.com/ssokolow/fastdupes"
                >ssokolow/fastdupes</a> on GitHub.
            </p>
        </div>
"""

PAGE_FOOTER = """
        <div class='footer'>
        <span class='generated'>""" + time.strftime("This page generated at %Y-%m-%d %H:%M UTC", time.gmtime()) + """</span>
        </div>
        <!-- Piwik -->
        <script type="text/javascript">
          var _paq = _paq || [];
          _paq.push(["trackPageView"]);
          _paq.push(["enableLinkTracking"]);

          (function() {
            var u=(("https:" == document.location.protocol) ? "https" : "http") + "://blog.ssokolow.com/stats/";
            _paq.push(["setTrackerUrl", u+"piwik.php"]);
            _paq.push(["setSiteId", "5"]);
            var d=document, g=d.createElement("script"), s=d.getElementsByTagName("script")[0]; g.type="text/javascript";
            g.defer=true; g.async=true; g.src=u+"piwik.js"; s.parentNode.insertBefore(g,s);
          })();
        </script>
        <noscript><img src="http://blog.ssokolow.com/stats/piwik.php?idsite=5&amp;rec=1" style="border:0" alt="" /></noscript>
        <!-- End Piwik -->
    </body>
</html>"""

#TODO: Make use of this regex to sanitize input before using it in HTML/XML.
#(Should also be sanitizing 0xD800-0xDFFF, 0xFFFE-0xFFFF, and 0x110000, but
# that has to wait until I've added support for parsing and honoring encoding
# declarations)
control_char_re      = re.compile('[\x00-\x09\x0B\x0C\x0E-\x1F]')

bad_anchor_char_re   = re.compile('[^A-Za-z0-9-_:.]+')
hyperlinkable_url_re = re.compile(r"""((?:ht|f)tps?://[^\s()]+(?:\([^\s()]*\)[^\s()]*)*)""", re.IGNORECASE | re.UNICODE)

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
    anchors = []        # Static

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
        _['anchor'] = bad_anchor_char_re.sub('_', _['filename']).lower()
        if not _['anchor'][0].isalpha():
            _['anchor'] = 'a' + _['anchor']

        # Ensure no duplicate anchors
        if _['anchor'] in self.anchors:
            count = 0
            while ('%s%d' % (_['anchor'], count)) in self.anchors:
                count += 1
            _['anchor'] = '%s%d' % (_['anchor'], count)
        self.anchors.append(_['anchor'])

        # Make sure that the filename will be used as a fallback program name.
        _['name'] = _['filename']

        # Actually extract the metadata.
        self._do_init()

        # Allow controlled truncation of module docstrings.
        for marker in ('--snip--', '--clip--'):
            if '\n%s\n' % marker in _['description']:
                _['description'] = _['description'].split('\n%s\n' % marker, 1)[0] + '\n[...]'

        # Add various pretty-printed and escaped values to the metadata dict.
        _.update({
            'fname_q': urllib.quote_plus(self.metadata['filename']),
            'fsize_p': formatFileSize(self.metadata['filesize']),
            'desc_e': xml_escape(self.metadata['description']),
            'mtime': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(self.metadata['filetime']))
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
        """Code to actually extract format-specific metadata goes here."""
        raise NotImplementedError("Cannot instantiate abstract class")

    def render(self, offline=False):
        if offline:
            self.metadata['get_url'] = self.metadata['filename']
        else:
            self.metadata['get_url'] = '?get=' + self.metadata['fname_q']

        output = '<div class="entry"><h2 id="%(anchor)s"><a ' % self.metadata

        if self.metadata['name'] == self.metadata['filename']:
            output += 'class="filename" '

        output += """href='%(get_url)s'>%(name)s</a>
            <a href="http://flattr.com/thing/414861/Stephan-Sokolow"
            style="vertical-align: middle"><img src="flattr_icon.png"
            alt="Flattr this" title="Flattr this" border="0" /></a>
            </h2>
            <ul class="attr_list">
                <li><span class="key">Size:</span> %(fsize_p)s
                </li>""" % self.metadata
        if self.metadata['version']:
            output += '\n<li><span class="key">Version:</span> %(version)s</li>\n' % self.metadata
        output += """<li><span class="key">License:</span> %(license_h)s</li>
                <li><span class="key">Language:</span> %(language)s</li>
                <li><span class="key">Last Modified:</span> %(mtime)s</li>
            </ul>
            <pre>%(desc_e)s</pre></div>""" % self.metadata
        return output

class PythonScriptEntry(ScriptEntry):
    shabang_re = re.compile('^#!(/usr(/local)?)?/bin/(env )?python')
    extensions = ['.py']

    _variable_re = r"""^%s\s*=\s*(?P<delim>'{1,3}|\"{1,3})(?P<value>.+?)(?P=delim)\s*$"""
    _metadata_regexes = {
            'license': re.compile(_variable_re % '__license__', re.MULTILINE),
            'name'   : re.compile(_variable_re % '__appname__', re.MULTILINE),
            'version': re.compile(_variable_re % '__version__', re.MULTILINE)
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
    """Use this as the replacement in a regex substitution with
    email_address_re to provide some degree of spam protection for e-mail
    addresses in docstrings.

    XXX: Should I add some randomness to the obfuscation approach?"""
    maps = {'@': ' at ', '.': ' dot '}

    email = match_obj.group(0)
    for char in maps:
        email = email.replace(char, maps[char])

    return email

def formatFileSize(size, unit='', precision=0):
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
    units = ['bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']

    if precision:
        size = float(size)

    # Did the calling function specify a valid unit of measurement?
    if unit and unit.upper() in units:         # If so, find the unit index by searching.
        unit_idx = units.index(unit)
        size /= (1024 ** unit_idx)
    else:                                      # If not, find the unit index by iteration.
        unit_idx = 0
        while abs(size) > 1024 and unit_idx < (len(units) - 1):
            size /= 1024
            unit_idx += 1

    return '%.*f %s' % (precision, size, units[unit_idx])

def list_content(path='.', offline=False):
    """Generate an HTML listing of available files, complete with metadata"""
    scripts, categories, path = [], [], os.path.abspath(path)

    for name in os.listdir(os.path.abspath(path)):
        fpath = os.path.join(path, name)

        if os.path.isdir(fpath):
            pass  # TODO: Support categories.
        else:
            ext = os.path.splitext(name)[1]
            for ec in entryClasses:
                if ext in ec.extensions:
                    scripts.append(ec(name))
                    continue

                lineOne = file(name).readline()
                if ec.shabang_re.match(lineOne):
                    scripts.append(ec(name))
    scripts.sort()

    output = [PAGE_HEADER]
    output.append("<div class='menu'><h2>Table of Contents</h2><ol>")
    for entry in scripts:
        tmp = '<li><a '

        #FIXME: De-duplicate this check. Do it properly.
        if entry.metadata['name'] == entry.metadata['filename']:
            tmp += 'class="filename" '

        tmp += "href='#%s'>%s</a></li>" % (entry.metadata['anchor'], entry.metadata['name'])
        output.append(tmp)
    output.append("</ol><hr><a href='..' class='backlink' rel='home'>Back to Parent Site</a></div>")
    output.append(BODY_HEADER)

    if categories:
        output.append("<h2>Categories</h2>")  # TODO: Add this to the table of contents.

    for entry in scripts:
        output.append(entry.render(offline=offline))
    output.append(PAGE_FOOTER)

    return '\n'.join(output)

if __name__ == '__main__':
    from optparse import OptionParser
    opt_parser = OptionParser(description=__doc__, version="%%prog v%s" % __version__)
    opt_parser.add_option('--offline', action="store_true", dest="offline",
        default=False, help="Generate a static index.html and .htaccess")

    # Allow pre-formatted descriptions
    opt_parser.formatter.format_description = lambda description: description

    opts, args = opt_parser.parse_args()

    if opts.offline:
        with open('index.html', 'w') as fh:
            fh.write(list_content(offline=True))
        with open('.htaccess', 'w') as fh:
            fh.write(HTACCESS)
    else:
        form = cgi.FieldStorage()
        if 'get' in form:
            print("Content-Type: text/html; charset=utf-8")
            print('')
            print(list_content())
        else:
            fname = os.path.normpath(form['get'].value)
            if not os.path.abspath(fname).startswith(os.getcwd()) or not os.path.isfile(fname):
                print("Content-Type: text/html; charset=utf-8")
                print('')
                print(PAGE_HEADER)
                print("<p>Unfortunately, you have requested an invalid file. "
                      "Please <a href='?'>try again</a>.</p>")
                print(PAGE_FOOTER)
            else:
                print("Content-Type: text/plain")
                print('')
                print(file(form['get'].value).read())
