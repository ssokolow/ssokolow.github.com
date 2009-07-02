#!/usr/bin/env python
"""
A convenience wrapper for building and installing a new kernel on Gentoo
Linux, complete with some extra bits to make maintaining a couple of
backup kernels easy. Also handles mounting and unmounting /boot and calling
module-rebuild to regenerate external kernel modules.

This only writes a tertiary kernel if none exists to prevent two builds
in a row from deleting the only good kernels available, so you'll want to
add this to your /etc/conf.d/local.start:

mount /boot
if [ -e /boot/old_kernel_emergency ]; then
	echo " * Boot considered successful. Purging tertiary kernel."
	rm -rf /boot/old_kernel_emergency
fi
umount /boot

Read the source for the rest of the details.

TODO:
- Should I have this regenerate the fbcondecor initrd?
- Better instructions. Possibly a zip bundle with a README
"""

import os, shutil, sys, time

kern_src = "/usr/src/linux"
kern_rel = os.path.join(kern_src,"include/config/kernel.release")
kern_arch = "x86_64"

kern_root = "/boot"
kern_main = os.path.join(kern_root, "kernel")
kern_backup = os.path.join(kern_root, "old_kernel")
kern_emergency = os.path.join(kern_root, "old_kernel_emergency") # This one will never be overwritten automatically

def die(msg, code=1):
	print msg
	sys.exit(code)

os.chdir(kern_src)
print "Making kernel"
os.system("make")

print "Mounting /boot"
os.system('mount "%s"' % kern_root)

print "Installing kernel modules for %s" % file(kern_rel).read().strip()
os.system("make modules_install")

for path in (kern_main, kern_backup, kern_emergency):
	if not os.path.exists(os.path.join(kern_root,path)):
		os.makedirs(path)

print "Backing up the current kernel"
if not os.path.isdir(kern_emergency) or not os.listdir(kern_emergency):
	# If the emergency kernel backup dir is nonexistant or empty, replace it with the current backup dir
	if os.path.exists(kern_emergency): os.rmdir(kern_emergency)
	os.rename(kern_backup, kern_emergency)
else:
	shutil.rmtree(kern_backup)
os.rename(kern_main, kern_backup)

print "Copying current kernel into place"
os.makedirs(kern_main)
shutil.copy(os.path.join(kern_src,'arch',kern_arch,'boot','bzImage'), os.path.join(kern_main, 'bzImage'))
shutil.copy(os.path.join(kern_src,'System.map'), os.path.join(kern_main, 'System.map'))
shutil.copy(os.path.join(kern_src,'.config'), os.path.join(kern_main, 'config'))
shutil.copy(kern_rel, os.path.join(kern_main, 'release'))

print "Unmounting /boot"
os.system('umount "%s"' % kern_root)

print "Regenerating external kernel modules"
for i in range(0,5):
	time.sleep(1)
	sys.stdout.write(".\a\t")
print
os.system('module-rebuild populate')
os.system('module-rebuild rebuild')
