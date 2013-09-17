#! /usr/bin/env python2


import ConfigParser as configparser
import argparse
import sys
import os


MP_PROG = os.path.basename(sys.argv[0])
MP_DIR = os.path.expanduser('~/.mp')


def msg(msg):
    print >>sys.stderr, msg

def dbg(what, value):
    msg('%s: %s' % (what, value))

def unlink_if_exists(file):
    if os.path.exists(file):
        os.unlink(file)


class Player:

    def __init__(self, options):
        self._options = options

    def _get_input_file(self, pid):
        return '%s/input-%u' % (MP_DIR, pid)

    def _get_play_cmd(self):
        return [ 'python2', '-c',
                'import sys; input = open(sys.argv[1], "r+");\nwhile True:\n sys.stdout.write(input.readline())',
                self._input_file ]

    def play(self):

        cleanup = []

        try:

            mp_pid = os.fork()
            if 0 == mp_pid:

                self._input_file = self._get_input_file(os.getpid())
                if not os.path.exists(MP_DIR):
                    os.mkdir(MP_DIR)
                os.mkfifo(self._input_file)

                cmd = self._get_play_cmd()
                cmd.insert(1, MP_PROG)
                if self._options.player_options is not None:
                    cmd.extend(self._options.player_options)
                cmd.append('--')
                cmd.extend(self._options.files)

                if self._options.debug:
                    dbg('cmd', cmd)

                os.execlp(*cmd)
                sys.exit(1)

            self._input_file = self._get_input_file(mp_pid)
            cleanup.append(lambda: unlink_if_exists(self._input_file))
            pid, status = os.waitpid(mp_pid, 0)

            return status >> 8

        finally:
            for fn in cleanup:
                fn()

    def _get_control_cmd(self):
        return self._options.cmd

    def control(self):

        input_file = self._get_input_file(self._options.pid)
        if not os.path.exists(input_file):
            msg('no input file for pid %u' % self._options.pid)
            return 1

        cmd = self._get_control_cmd()

        if self._options.debug:
            dbg('cmd', cmd)

        input = open(input_file, 'w')
        input.write(cmd + '\n')
        input.close()

        return 0


class MPV(Player):

    _commands = {
        'pause': 'set pause yes',
        'resume': 'set pause no',
    }

    def _get_play_cmd(self):
        cmd = [ 'mpv' ]
        if self._options.profile is not None:
            cmd.append('--profile=%s' % self._options.profile)
        if not sys.stdout.isatty():
            cmd.append('--msglevel=cache=3:statusline=3')
        if self._options.verbose:
            cmd.append('-v')
        cmd.append('--input-file=%s' % self._input_file)
        return cmd

    def _get_control_cmd(self):
        return self._commands[self._options.cmd]


class MPlayer(Player):

    _commands = {
        'pause': 'pausing_keep_force pause',
        'resume': 'seek +0',
    }

    def _get_play_cmd(self):
        cmd = [ 'mplayer' ]
        if self._options.profile is not None:
            cmd.extend(['-profile', self._options.profile])
        if not sys.stdout.isatty():
            cmd.extend(['-msglevel', 'cache=3:statusline=3'])
        if self._options.verbose:
            cmd.append('-v')
        cmd.extend(['-input', 'file=%s' % self._input_file])
        return cmd

    def _get_control_cmd(self):
        return self._commands[self._options.cmd]


parser = argparse.ArgumentParser(prog=MP_PROG)

parser.add_argument('-p', '--player',
                    choices=['mpv', 'mplayer', 'dummy'], default='mpv',
                    help='select player to use')
parser.add_argument('-d', '--debug',
                    action='store_true', default=False,
                    help='enable debug traces')

if 'mp-play' == MP_PROG:

    parser.add_argument('--option',
                        metavar='OPTION', action='append', dest='player_options',
                        help='add an option to be passed to the underlying player')
    parser.add_argument('--profile',
                        help='select the specified configuration profile')
    parser.add_argument('-v', '--verbose',
                        action='store_true', default=False,
                        help='enable verbose mode')

    parser.add_argument('files', nargs='+')

elif 'mp-control' == MP_PROG:

    parser.add_argument('pid', type=int, help='PID of the player to control')
    parser.add_argument('cmd', choices=['pause', 'resume'], help='command to send to player')

else:
    print >>sys.stderr, 'invalid mode: %s' % MP_PROG
    sys.exit(1)


args = []

config_file = '%s/config' % MP_DIR
if os.path.exists(config_file):

    config = configparser.RawConfigParser(allow_no_value=True)
    config.read(config_file)

    for section in ('default', MP_PROG):
        if config.has_section(section):
            for k, v in config.items(section):
                opt_name = '--' + k
                if v is None:
                    args.append(opt_name)
                    continue
                for opt_val in v.split():
                    args.append('%s=%s' % (opt_name, opt_val))

args.extend(sys.argv[1:])

options = parser.parse_args(args)

if options.debug:
    dbg('args', args)
    dbg('options', options)

klass = {
    'mpv': MPV,
    'mplayer': MPlayer,
    'dummy': Player,
}[options.player]

player = klass(options)

if 'mp-play' == MP_PROG:
    ret = player.play()
elif 'mp-control' == MP_PROG:
    ret = player.control()

sys.exit(ret)

