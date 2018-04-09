#!/usr/bin/env python2

import subprocess
import optparse
import struct
import signal
import copy
import time
import sys
import re
import os


def check_display(option, opt, value):
    m = re.match('^\d+$', value)
    if not m:
        raise optparse.OptionValueError('invalid display ID: %s' % value)
    return int(m.group(0))

def check_geometry(option, opt, value):
    m = re.match('^(\d+)x(\d+)(:(\d+)x(\d+))?$', value)
    if not m:
        raise optparse.OptionValueError('invalid display geometry: %s' % value)
    width, height = int(m.group(1)), int(m.group(2))
    if m.group(3):
        horizontal_screens, vertical_screens = int(m.group(4)), int(m.group(5))
    else:
        horizontal_screens, vertical_screens = 1, 1
    return (width, height, horizontal_screens, vertical_screens)

class Option(optparse.Option):

    TYPES = optparse.Option.TYPES + ('display', 'geometry',)
    TYPE_CHECKER = copy.copy(optparse.Option.TYPE_CHECKER)
    TYPE_CHECKER['display'] = check_display
    TYPE_CHECKER['geometry'] = check_geometry


parser = optparse.OptionParser(option_class=Option)
parser.add_option('-D', '--display',
                  dest='display', metavar='DISPLAY', default=2, type='display',
                  help='X11 display ID to use')
parser.add_option('-g', '--geometry',
                  dest='geometry', metavar='WxH[:WxH]', default='1024x768', type='geometry',
                  help='display geometry: total width/height (pixels), width/height (screens, optional, default to 1x1)')
parser.add_option('-d', '--debug',
                  action='store_true', dest='debug', default=False,
                  help='enable debug traces')

(options, args) = parser.parse_args()


xsession_debug = options.debug


class SigException():

    def __init__(self, signum):
        self.signum = signum


def xsession_sighandler(signum, frame):
    if xsession_debug:
        if signal.SIGUSR1 == signum:
            signame = 'SIGUSR1'
        elif signal.SIGUSR2 == signum:
            signame = 'SIGUSR2'
        else:
            signame = str(signum)
        print 'xsession_sighandler(' + signame + ')'
    raise SigException(signum)


signal.signal(signal.SIGUSR1, xsession_sighandler)
signal.signal(signal.SIGUSR2, xsession_sighandler)


def dim_split(dim, num):
    step = dim / num
    values = []
    for d in range(num - 1):
        values.append(step)
        dim -= step
    values.append(dim)
    return values

def display_geometry_to_screens(display_width, display_height,
                                horizontal_screens, vertical_screens):
    screens_widths = dim_split(display_width, horizontal_screens)
    screens_heights = dim_split(display_height, vertical_screens)
    screens = []
    x, y = 0, 0
    for w in screens_widths:
        for h in screens_heights:
            screens.append((x, y, w, h))
            y = (y + h) % display_height
        x = (x + w) % display_width
    return screens

xephyr_display = ':%u' % options.display
xephyr_pid = os.fork()
if 0 == xephyr_pid:
    # This will make the xserver send us a SIGUSR1 when ready.
    signal.signal(signal.SIGUSR1, signal.SIG_IGN)
    xephyr_cmd = [
        'Xephyr', 'Xephyr',
        xephyr_display,
        '+xinerama',
        '-ac',
        '-noreset',
        '-extension', 'GLX',
    ]
    screens = display_geometry_to_screens(*options.geometry)
    for x, y, w, h in screens:
        xephyr_cmd.extend([
            '-origin', '%u,%u' % (x, y),
            '-screen', '%ux%u' % (w, h),
        ])
    if xsession_debug:
        print 'starting xephyr:', ' '.join(xephyr_cmd)
    os.execlp(*xephyr_cmd)

xsession_signum = None

try:

    # Wait for xserver to be ready.

    if xsession_debug:
        print 'waiting for xserver to be ready'

    try:
        signal.pause()
    except KeyboardInterrupt:
        sys.exit(0)
    except SigException, e:
        assert signal.SIGUSR1 == e.signum

    if xsession_debug:
        print 'xserver ready'

    os.system('xrdb -query | xrdb -load -display %s -' % xephyr_display)

    # Ugly hack... using xkbcomp only work after a least one keypress...
    os.system('xdotool key space')
    os.system('xkbcomp %s %s' % (os.environ['DISPLAY'], xephyr_display))

    os.environ['DISPLAY'] = xephyr_display

    if xsession_debug:
        print 'starting dbus'

    dbus_cmd = ['dbus-launch', '--binary-syntax']
    dbus = subprocess.Popen(dbus_cmd, stdout=subprocess.PIPE)
    dbus_env = dbus.communicate()[0]
    ulong_size = struct.calcsize('L')
    uint_size = struct.calcsize('I')
    dbus_pid, = struct.unpack('I', dbus_env[-(ulong_size+uint_size):-ulong_size])
    dbus_xid, = struct.unpack('L', dbus_env[-ulong_size:])
    dbus_address = dbus_env[:-(ulong_size+ulong_size+1)]

    if xsession_debug:
        print 'dbus_pid:', dbus_pid
        print 'dbus_xid:', dbus_xid
        print 'dbus_address:', dbus_address

    try:

        xsession_pid = os.getpid()
        os.environ['XSESSION_PID'] = str(xsession_pid)
        os.environ['DBUS_SESSION_BUS_ADDRESS'] = dbus_address

        if xsession_debug:
            print 'xsession_pid:', xsession_pid

        wm_args = args[:]
        if 0 == len(wm_args):
            wm_args = [ 'xterm' ]

        if xsession_debug:
            print 'starting wm:', ' '.join(wm_args)

        wm_pid = os.fork()
        if 0 == wm_pid:
            os.execvp(wm_args[0], wm_args)

        if xsession_debug:
            print 'wm_pid:', wm_pid

        while True:
            try:
                os.waitpid(wm_pid, 0)
                break
            except KeyboardInterrupt:
                sys.exit(0)
            except SigException, e:
                xsession_signum = e.signum

        if xsession_debug:
            print 'wm terminated'

    finally:

        if xsession_debug:
            print 'killing dbus'

        os.kill(dbus_pid, signal.SIGTERM)

finally:

    if xsession_debug:
        print 'killing xserver'

    os.kill(xephyr_pid, signal.SIGTERM)
    os.waitpid(xephyr_pid, 0)

    if xsession_debug:
        if signal.SIGUSR1 == xsession_signum:
            print 'wm asked for reboot'
        elif signal.SIGUSR2 == xsession_signum:
            print 'wm asked for halt'

