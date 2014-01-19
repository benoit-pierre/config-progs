#!/usr/bin/env python2

import os
import sys
import time
import socket
import xmlrpclib
import subprocess

s = xmlrpclib.ServerProxy('http://localhost:6800/rpc')

version = None
for retry in xrange(40):
    try:
        version = s.aria2.getVersion()
        break
    except socket.error:
        if 0 == retry:
            aria2_dir = os.path.expanduser('~/.aria2')
            if not os.path.exists(aria2_dir):
                os.mkdir(aria2_dir)
            aria2_session = '%s/session' % aria2_dir
            cmd = ['term', '-t', 'downloader', '-nw',
                   'aria2c',
                   '--check-certificate=true',
                   '--disable-ipv6=true',
                   '--enable-rpc=true',
                   '--max-concurrent-downloads=1',
                   '--save-session', aria2_session
                  ]
            if os.path.exists(aria2_session):
                cmd.extend(['--input-file', aria2_session])
            subprocess.Popen(cmd)
        time.sleep(0.1)

if version is None:
    sys.exit(1)

if 1 == len(sys.argv):
    sys.exit(0)

print >>sys.stderr, 'aria2', version

key = None
options = {}
for arg in sys.argv[1:]:
    if arg.startswith('--'):
        key = arg[2:]
    elif key is not None:
        options[key] = arg

referer = options.get("referer", None)
print >>sys.stderr, 'referer:', referer

options['dir'] = os.path.expanduser('~/downloads')

uris = options.pop('uris')
if type(uris) is str:
    uris = [ uris ]

options['always-resume'] = 'true'
options['auto-file-renaming'] = 'false'

global_options = {}
for key in []: #['load-cookies']:
    if key not in options:
        continue
    global_options[key] = options.pop(key)

print >>sys.stderr, uris, options, global_options

s.aria2.changeGlobalOption(global_options)
s.aria2.addUri(uris, options)

