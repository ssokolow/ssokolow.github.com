#!/usr/bin/env python
"""
A quick-access auto-saving, auto-hiding scratchpad for jots, multi-step
copy-pasting, and anything else where a more specialized app is over-thinking
the problem and opening a plain old plaintext editor (like leafpad, notepad, or
kedit) is inefficient and potentially clutter-inducing.

Requires: PyGTK
Recommended: GtkSourceView and its Python bindings (Undo/Redo support)
Usage: Run it and then click the white line along the left edge of the desktop.
       (Also supports drag-and-drop)

TODO:
- Include a "pushpin" icon/button in the lower-right corner to lock the tray open.
- Pressing escape should collapse the tray
- Implement some form of multi-note support for storing stuff that needs to be
  "backgrounded". Maybe tabbing. (Similar reason to having a few virtual
  desktops)
- Support some sort of resize handle or handles.

Known Bugs:
- The window hides while the context menu is visible (harmless but unintuitive)
- Quitting by closing the X connection (xkill) doesn't commit pending changes.
- A drag-and-drop which sends a drag motion event to this but then ends in a
  drop to another window will temporarily confuse the auto-hide.
- ScratchTray currently depends on fcntl... which is non-portable. I'll update
  it to use a portable wrapper once I've made appropriate preparations so that
  my index.cgi script accepts zipped bundles.
  (http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/65203)
- Resizing the tray on resolution change is currently broken. I'll take a look
  at it soon.
"""

__appname__ = "ScratchTray"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2 or later"

import pygtk
pygtk.require('2.0')
import fcntl, gobject, gtk, os, signal, sys, tempfile

TICK_INTERVAL = 5000          # Milliseconds of inactivity before save-to-disk
HANDLE_SIZE   = 2             # Width of the window when "hidden"
PAD_SIZE      = (0.45, 0.60)  # The size of the pad as decimal percentages.
WRAP_MODE     = gtk.WRAP_WORD # Don't break up words when word-wrapping.
DISK_FILE     = os.path.expanduser(os.path.join('~','.scratch'))

try:
	import gtksourceview
	_TextView = gtksourceview.SourceView
	_TextBuffer = gtksourceview.SourceBuffer
except ImportError:
	try:
		import gtksourceview2
		_TextView = gtksourceview2.SourceView
		_TextBuffer = gtksourceview2.SourceBuffer
	except ImportError:
		_TextView = gtk.TextView
		_TextBuffer = gtk.TextBuffer

class ScratchTray:
    has_mouse, has_keyboard = False, False
    pending_timeout = None

    def __init__(self, diskFile=DISK_FILE):
        # create the widgets
        self.diskFile = diskFile
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.frame = gtk.Frame()

        self.sw = gtk.ScrolledWindow()
        self.pad = _TextView(_TextBuffer())
        self.buf = self.pad.get_buffer()
        self.screen = gtk.gdk.screen_get_default()

        # Tie them together
        self.sw.add(self.pad)
        self.frame.add(self.sw)
        self.window.add(self.frame)

        # Set up the TextView
        self.sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.pad.set_wrap_mode(WRAP_MODE)

        try:
            if os.path.exists(diskFile):
                self.fh = open(diskFile,'rU+')
                self.buf.set_text(self.fh.read())
            else:
                self.fh = open(diskFile,'w')
            # Prevent two copies from walking over each others' data.
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print "ERROR: Could not acquire exclusive lock on data file."
            sys.exit(0)

		# This has to be done before hooking the changed event to be effective.
        self.buf.set_modified(False)
        self.pad.set_editable(True)

        # Hook the events
        self.window.connect("destroy", self.destroy)
        #self.window.connect("enter_notify_event", self.cb_event_toggle, 'has_mouse', True)
        self.window.connect("leave_notify_event", self.cb_event_toggle, 'has_mouse', False)
        self.window.connect("focus-in-event", self.cb_event_toggle, 'has_keyboard', True)
        self.window.connect("focus-out-event", self.cb_event_toggle, 'has_keyboard', False)
        self.window.connect('drag_motion', self.cb_drag_motion)
        self.buf.connect("changed", self.cb_modified)
        self.screen.connect("size-changed", self.update_pad_geom)
        self.window.drag_dest_set(0, [], 0)

        # The final step is to display this newly created widget.
        self.frame.set_border_width(1)
        self.frame.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        self.window.set_gravity(gtk.gdk.GRAVITY_WEST)
        self.update_pad_geom()
        self.window.show_all()

    def update_pad_geom(self, screen=None):
        #Get the height and width of the Center-left monitor for this screen
        monitor = self.screen.get_monitor_at_point(0, gtk.gdk.screen_height() / 2)
        self.screen_geom = self.screen.get_monitor_geometry(monitor)

        width  = int(self.screen_geom.width  * PAD_SIZE[0])
        height = int(self.screen_geom.height * PAD_SIZE[1])
        x, y = 0, int((self.screen_geom.height - height) / 2)

        self.pad_geom = gtk.gdk.Rectangle(x, y, width, height)
        self.updatePos()

    def saveScratch(self):
        if self.buf.get_modified():
            start, end = self.buf.get_bounds()
            chars = self.buf.get_slice(start, end, False)
            try:
                fd, fn = tempfile.mkstemp(prefix='.',dir=os.path.dirname(self.diskFile),text=True)
                file = os.fdopen(fd, 'w')
                file.write(chars)
                file.flush()
                os.fsync(file.fileno())

                self.fh.close()
                self.fh = file
                fcntl.flock(self.fh, fcntl.LOCK_EX)
                os.rename(fn, self.diskFile)

                self.buf.set_modified(False)
            except IOError, (errnum, errmsg):
                err = "Unable to save contents.  Error writing to '%s': %s" % (self.diskFile, errmsg)
                dialog = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, err)
                dialog.set_title("ScratchTray")
                dialog.run()
                dialog.destroy()

    def onExit(self):
        self.saveScratch()
        self.fh.close()

    def updatePos(self):
        self.window.stick()
        self.window.set_keep_above(True)
        self.window.set_decorated(False)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)

        _h = self.pad_geom.height
        if self.has_mouse or self.has_keyboard:
            _w = self.pad_geom.width
        else:
            _w = HANDLE_SIZE

        self.window.set_size_request(_w, _h)
        self.window.set_geometry_hints(None, min_width=_w, min_height=_h, max_width=_w, max_height=_h)
        #self.window.resize(_w, _h)
        self.window.move(self.pad_geom.x, self.pad_geom.y)

    def cb_drag_motion(self, wid, context, x, y, time):
        setattr(self, 'has_mouse', True)
        self.updatePos()

    def cb_modified(self, buf):
        if self.pending_timeout:
            gobject.source_remove(self.pending_timeout)
        self.pending_timeout = gobject.timeout_add(TICK_INTERVAL, self.saveScratch)

    def cb_event_toggle(self, widget, event, toggle, status):
        setattr(self, toggle, status)
        self.updatePos()

    def destroy(self, widget, data=None):
        """This callback fires when the window is destroyed.
        It saves the scratchpad and then quits."""
        self.saveScratch()
        gtk.main_quit()

if __name__ == "__main__":
    app = ScratchTray()

	# Make sure that ScratchTray saves to disk on exit.
    sys.exitfunc = app.onExit
    signal.signal(signal.SIGTERM, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGHUP, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGQUIT, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGINT, lambda signum, stack_frame: sys.exit(0))

    try:
    	gtk.main()
    except KeyboardInterrupt:
		sys.exit(0)

