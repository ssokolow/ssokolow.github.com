#!/usr/bin/env python
"""
kde_gui_fixes.py

A quick script to fix a couple of my KDE pet peeves:
- The screensaver disabling mechanism doesn't guarantee it'll get re-enabled.
- There's no way to ensure scrolling in the corners will switch desktops.

Requires: PyGTK, PyDCOP (optional, default configuration only)
(I used PyGTK because I'm more familiar with it than PyQt and I was rushed)

Some code based on the shaped window example from the PyGTK 2.x tutorial.

TODO:
- Merge this with another idea of mine and whip up a nice GUI for it.
"""

__appname__ = "KDE GUI Fixes"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.1alpha1"
__license__ = "GNU GPL 2.0 or newer"

import pygtk
pygtk.require('2.0')
import gtk, gobject, logging

import time, pydcop
kwin = pydcop.anyAppCalled('kwin')

SCROLL_ACTIONS = {
    gtk.gdk.SCROLL_DOWN   : lambda w,e : kwin.KWinInterface.nextDesktop(),
    gtk.gdk.SCROLL_UP : lambda w,e : kwin.KWinInterface.previousDesktop()
}

BUTTON_ACTIONS = {
    1 : lambda w,e : pydcop.anyAppCalled('kdesktop').KDesktopIface.popupExecuteCommand(),
    2 : lambda w,e : pydcop.anyAppCalled('kicker').kicker.toggleShowDesktop(),
    3 : lambda w,e : pydcop.anyAppCalled('kicker').kicker.popupKMenu(tuple(int(x) for x in e.get_root_coords()))
}

ACTIVE_CORNERS = (gtk.gdk.GRAVITY_NORTH_WEST, gtk.gdk.GRAVITY_NORTH_EAST,
                  gtk.gdk.GRAVITY_SOUTH_WEST, gtk.gdk.GRAVITY_SOUTH_EAST)

logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)-8s %(message)s',)

def close_daemon(widget, event, data=None):
    """A GTK+ callback to be used by events which should cleanly exit the daemon."""
    gtk.main_quit()
    return False

class ModuleBase(object):
    """Base class for feature modules

    Note: __init__() and activate() are separated to allow users to deactivate
    and reactivate modules interactively without having to serialize all state
    to disk to avoid it being lost."""
    name = None
    isConfigurable = False

    def activate(self):
        """Called when the user requests the service be activated."""
        raise NotImplementedError("All modules must activate via this method.")
    def deactivate(self):
        """Called when the user requests the service be deactivated."""
        raise NotImplementedError("All modules must allow deactivation without daemon exit.")
    def configure(self):
        """Called when the user requests a configuration dialog."""
        raise NotImplementedError("This plugin has no configuration options.")

class TriggerCorners(ModuleBase):
    """
    A simple little tool to allow binding of actions to the mouse buttons and
    scroll wheel when the pointer is in one or more of the desktop corners.
    Mimicks MacOS 7 rounded desktop corners as a side-effect. (I'll add support
    for using composited transparency to avoid it once KDE 4 is comfortable)

    The default configuration uses PyDCOP to map mouse scrolling to
    desktop switching and right-clicking to the K menu (Behaviour
    identical to my system when using a WinDeco theme where the
    corners stay rounded when maximized) but there is no in-built
    dependency on any specific desktop environment.

    Trivial code editing is required to edit the configuration and
    allows mapping of actions to any scroll direction or mouse button as well
    as disabling specific corners. (eg. to prevent them from interfering with
    Compiz Fusion edge actions)

    TODO:
    - Check whether Window.show_all() will do instead of multiple show() calls.
    """
    # This is untested and apparently doesn't work with Compiz Fusion despite
    # it following the PyGTK docs.
    CORNER_OPACITY = 0.5
    CORNER_MASK = [
        "4 4 2 1",
        "       c None",
        "X      c #000000000000",
        "XXXX",
        "XX  ",
        "X   ",
        "X   "
    ]

    class Corner(gtk.Window):
        """The implementation for event-sensitive desktop corner widgets."""
        def _set_corner(self, gravity):
            """Place the widget in its assigned corner of the desktop."""
            if gravity is gtk.gdk.GRAVITY_NORTH_WEST:
                self.set_gravity(gtk.gdk.GRAVITY_NORTH_WEST)
                self.move(0, 0)
                self.mask_pixbuf = self.base_mask.rotate_simple(0)
                # Might as well ensure that a duplicate is made even if no rotation
                # occurs. Reduced chance for odd behaviour that way.

            elif gravity is gtk.gdk.GRAVITY_SOUTH_WEST:
                self.set_gravity(gtk.gdk.GRAVITY_SOUTH_WEST)
                self.move(0,gtk.gdk.screen_height()-self.base_mask.get_height())
                self.mask_pixbuf = self.base_mask.rotate_simple(90)

            elif gravity is gtk.gdk.GRAVITY_SOUTH_EAST:
                self.set_gravity(gtk.gdk.GRAVITY_SOUTH_EAST)
                self.move(gtk.gdk.screen_width() - self.base_mask.get_width(),
                    gtk.gdk.screen_height() - self.base_mask.get_height())
                self.mask_pixbuf = self.base_mask.rotate_simple(180)

            elif gravity is gtk.gdk.GRAVITY_NORTH_EAST:
                self.set_gravity(gtk.gdk.GRAVITY_NORTH_EAST)
                self.move(gtk.gdk.screen_width() - self.base_mask.get_width(),0)
                self.mask_pixbuf = self.base_mask.rotate_simple(270)

            else:
                raise TypeError("Invalid gravity for Corner")

        def __init__(self, gravity, pixbuf, opacity=None):
            gtk.Window.__init__(self, gtk.WINDOW_POPUP)
            self.set_events(self.get_events() | gtk.gdk.SCROLL_MASK)

            self.base_mask = pixbuf
            self._set_corner(gravity)

            if opacity is not None:
                self.set_opacity(opacity)
                #FIXME: set_opacity seems to have no effect in Compiz Fusion.

            self.pixmap, self.mask = self.mask_pixbuf.render_pixmap_and_mask()

            image = gtk.Image()
            image.set_from_pixmap(self.pixmap, self.mask)
            image.show()

            fixed = gtk.Fixed()
            fixed.set_size_request(*self.pixmap.get_size())
            fixed.put(image, 0, 0)
            self.add(fixed)
            fixed.show()

            self.shape_combine_mask(self.mask, 0, 0)

    def scroll_handler(self, widget, event, data=None):
        if event.direction in SCROLL_ACTIONS:
            SCROLL_ACTIONS[event.direction](widget, event)

    def button_handler(self, widget, event, data=None):
        if event.button in BUTTON_ACTIONS:
            BUTTON_ACTIONS[event.button](widget, event)

    def __init__(self):
        base_mask = gtk.gdk.pixbuf_new_from_xpm_data(self.CORNER_MASK)

        self.corners = []
        for direction in ACTIVE_CORNERS:
            corner = self.Corner(direction, base_mask, self.CORNER_OPACITY)
            #XXX: Do we want to close the daemon or just this service?
            corner.connect("delete_event", close_daemon)
            corner.connect("scroll-event", self.scroll_handler)
            corner.connect("button-press-event", self.button_handler)
            self.corners.append(corner)

    def activate(self):
        [x.show() for x in self.corners]
    def deactivate(self):
        [x.hide() for x in self.corners]

class KScreensaverFixer(ModuleBase):
    """
    A workaround for KDE's poorly thought out system for disabling the screensaver.

    Re-enables the screensaver if it stays disabled for more than
    TIMEOUT_DURATION, checking every SLEEP_DURATION. (defaults are two hours and
    one minute, respectively)
    """
    name = "KScreensaverFixer"
    TIMEOUT_DURATION = 2 * 3600 # two hours
    SLEEP_DURATION = 60 # one minute

    def __init__(self):
        import pydcop
        self._wait_start = None
        #FIXME: The following line will probably break things if I have to restart kdesktop.
        self._kdesktop = pydcop.anyAppCalled('kdesktop')
        self._tid = None

    def activate(self):
        self._tid = gobject.timeout_add(self.SLEEP_DURATION * 1000, self._watcher_cb)
    def deactivate(self):
        if self._tid: gobject.source_remove(self._tid)
        self._tid = None

    def _watcher_cb(self):
        if bool(self._kdesktop.KScreensaverIface.isEnabled()):
            self._wait_start = None
        else:
            self._wait_start = self._wait_start or time.time()
            if time.time() >= (self._wait_start + self.TIMEOUT_DURATION):
                self._kdesktop.KScreensaverIface.enable(True)
                self._wait_start = None
        return True

desired_modules = [TriggerCorners, KScreensaverFixer]

if __name__ == "__main__":
    active_modules = []
    for Module in desired_modules:
        try:
            module = Module()
            module.activate()
            active_modules.append(module)
        except Exception, err:
            import traceback
            name = Module.name if Module.name is not None else Module
            logging.error("Unable to load module: %s" % name, )
            logging.debug(traceback.format_exc())
    gtk.main()
