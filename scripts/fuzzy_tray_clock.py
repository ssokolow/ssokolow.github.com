#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A simple clone of the KDE Fuzzy Clock widget for use in other desktops.
The time appears as a tooltip if you hover your mouse over the tray icon.

If you'd like additional levels of fuzziness, just ask.
"""

__appname__ = "Fuzzy Tray Clock"
__version__ = "0.1"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

UPDATE_INTERVAL = 60    # in Seconds
DEFAULT_ICON = 'xclock'

import pygtk
pygtk.require('2.0')
import gtk, gobject, time

# Credit to the Fuzzy Clock plasma widget for this and the "time / 3" indexing.
# I borrowed them from fuzzyClock.cpp in kdeplasma-addons-4.1.85.tar.bz2
dayTime = ["Night", "Early morning", "Morning", "Almost noon",
           "Noon", "Afternoon", "Evening", "Late evening"]

class FuzzyTray:
    def __init__(self, icon=None):
        self.icon = gtk.StatusIcon()
        self.update_clock() # Don't wait 1 second before creating the first tooltip
        gobject.timeout_add(1000 * UPDATE_INTERVAL, self.update_clock)

        if icon:
            self.icon.set_from_file(icon)
        else:
            self.icon.set_from_icon_name(DEFAULT_ICON)

    def update_clock(self):
        hour = time.localtime()[3]
        fuzzyTime = dayTime[hour // 3]
        self.icon.set_tooltip(fuzzyTime)
        return True # Make the timeout callback repeat again and again

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser(version="%s v%s" % (__appname__, __version__))
    parser.add_option('--icon', action="store", dest="icon",
        default=None, metavar="PATH", help="Set a custom icon")

    opts, args = parser.parse_args()
    app = FuzzyTray(opts.icon)
    gtk.main()
