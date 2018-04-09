#!/usr/bin/env python3

__requires__ = '''
xattr >= 0.9.3
'''

import argparse
import configparser
import mimetypes
import os
import re
import shlex
import subprocess
import sys
import textwrap

from xattr import xattr


MP_PROG = os.path.basename(sys.argv[0])
MP_DIR = '%s/mp' % os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))


def msg(msg):
    print(msg, file=sys.stderr)

def dbg(what, value):
    msg('%s: %s' % (what, value))

def dbg_cmd(cmd):
    dbg('cmd', ' '.join(shlex.quote(a) for a in cmd))

def unlink_if_exists(file):
    if os.path.exists(file):
        os.unlink(file)


class LoudnessDatabase(object):

    FATTR = 'user.loudness'
    NULL = open(os.devnull, 'r+b')

    def __init__(self, midvol, maxvol):
        self._midvol = float(midvol)
        self._maxvol = float(maxvol)

    def get_loudness(self, path):
        fattrs = xattr(path)
        if self.FATTR in fattrs:
            lufs, peak = [float(v) for v in fattrs[self.FATTR].split()]
            return lufs, peak
        lufs, peak = self._calculate_loudness(path)
        if lufs is None:
            return None, None
        value = b'%f %f' % (lufs, peak)
        fattrs[self.FATTR] = value
        return lufs, peak

    def get_volume(self, path):
        lufs, peak = self.get_loudness(path)
        if lufs is None:
            return None
        return 100 * 10 ** ((self._midvol + min(self._maxvol-lufs, -peak)) / 60)

    def _calculate_loudness(self, path):
        output = subprocess.check_output(
            'loudness --force-plugin=ffmpeg scan -p dbtp'.split() +
            [path], stderr=self.NULL,
        )
        last_line = output.decode().strip().split('\n')[-1]
        m = re.match(r'^\s*(-?[0-9.]+) LUFS,\s*(-?[0-9.]+) dBTP$', last_line)
        if m is None:
            if re.match(r'\s*-inf LUFS,\s*-inf dBTP$', last_line) is not None:
                return 0, 0
            return None, None
        lufs, peak = float(m.group(1)), float(m.group(2))
        return lufs, peak


class Player:

    _klasses = {}

    _SUBDOWNLOADERS = (
        'periscope',
        'subberthehut',
        'subdownloader',
    )

    _SUBEXTS = set((
        '.srt',
        '.sub',
    ))

    @staticmethod
    def from_name(name, options):
        klass = Player._klasses[name]
        player = klass(options)
        return player

    @staticmethod
    def from_pid(pid, options):
        name = os.readlink('/proc/%u/exe' % pid)
        if name.endswith(' (deleted)'):
            name = name[:-10]
        name = os.path.basename(name)
        return Player.from_name(name, options)

    def __init__(self, options):
        self._options = options
        self._dev_null = open('/dev/null', 'w')

    @staticmethod
    def _get_input_file(pid):
        return '%s/input-%u' % (MP_DIR, pid)

    def _get_play_cmd(self):
        return [
            sys.executable, '-c',
            textwrap.dedent(
                '''
                import sys
                input = open(sys.argv[1], "r+")
                while True:
                    sys.stdout.write(input.readline())
                '''),
            self._input_file,
        ]

    def _nvperf(self, mode):
        from nvperf import nvperf
        if self._options.debug:
            dbg('nvperf', mode)
        nvperf(mode, verbose=self._options.verbose)

    @staticmethod
    def _is_video(fp):
        ''' Check if file is a video file. '''
        mimetypes.init()
        mtype, __ = mimetypes.guess_type(fp)
        if mtype is None:
            return False
        return mtype.startswith('video/')

    def _need_subtitles(self, file):
        ''' Do we need subtitles for this file? '''
        directory = os.path.dirname(os.path.realpath(file))
        if directory[-1] != '/':
            directory += '/'
        for path in self._options.fetch_subtitles:
            if path[-1] != '/':
                path += '/'
            if path[0] == '!' and directory.startswith(path[1:]):
                return False
            if directory.startswith(path):
                return True
        return False

    def _has_subtitles(self, file):
        ''' Check if subtitles for the specified file exists. '''
        file_name, __ = os.path.splitext(os.path.basename(file))
        for entry in os.listdir(os.path.dirname(os.path.abspath(file))):
            name, ext = os.path.splitext(entry)
            if ext.lower() not in self._SUBEXTS:
                continue
            if name.lower() == file_name.lower():
                return True
        return False

    def _call_subtitles_downloader(self, cmd):
        if self._options.debug:
            dbg_cmd(cmd)
        if self._options.debug:
            stdout = sys.stdout
            stderr = sys.stderr
        else:
            stdout = self._dev_null
            stderr = subprocess.STDOUT
        try:
            return subprocess.call(cmd, stdout=stdout, stderr=stderr)
        except OSError as e:
            if self._options.debug:
                dbg('exception', e)
            return -1

    def _fetch_subtitles_periscope(self, file):
        cmd = [
            'periscope',
            '--language', self._options.subtitles_language,
            '--quiet',
            file,
        ]
        return self._call_subtitles_downloader(cmd) == 0

    def _fetch_subtitles_subberthehut(self, file):
        cmd = [
            'subberthehut',
            '--lang', self._options.subtitles_language,
            '--hash-search-only',
            '--never-ask',
            '--same-name',
            '--quiet',
            file,
        ]
        return self._call_subtitles_downloader(cmd) == 0

    def _fetch_subtitles_subdownloader(self, file):
        cmd = [
            'subdownloader',
            '--lang', self._options.subtitles_language,
            '--video', os.path.abspath(file),
            '--rename-subs',
            '--cli', '-D',
        ]
        if self._call_subtitles_downloader(cmd) != 0:
            return False
        # Need to check ourself if subtitles were found since subdownloader
        # error code does not indicate it.
        return self._has_subtitles(file)

    def _fetch_subtitles(self):

        if not self._options.fetch_subtitles:
            return

        mimetypes.init()

        for fname in self._options.files:

            if not os.path.exists(fname):
                continue

            if not self._is_video(fname):
                continue

            if not self._need_subtitles(fname):
                continue

            if self._has_subtitles(fname):
                continue

            if self._options.debug or self._options.verbose:
                msg('fetching subtitles for %s' % fname)

            for downloader in self._SUBDOWNLOADERS:
                if self._options.debug or self._options.verbose:
                    msg('trying with %s' % downloader)
                fn = getattr(self, '_fetch_subtitles_' + downloader)
                if fn(fname):
                    break
            else:
                if self._options.debug or self._options.verbose:
                    msg('no subtitles were found')

    def _calculate_volume(self):
        database_path = os.path.join(MP_DIR, 'loudness.db')
        db = LoudnessDatabase(-23, -13)
        min_volume = None
        for fname in self._options.files:
            if not os.path.isfile(fname):
                continue
            if self._options.debug or self._options.verbose:
                msg('calculating volume for %s' % fname)
            volume = db.get_volume(fname)
            if volume is None:
                continue
            if min_volume is None or min_volume > volume:
                min_volume = volume
        if min_volume is None:
            min_volume = 35
        else:
            min_volume = min(min_volume, 65)
        volume = int(round(min_volume))
        return volume

    def play(self):

        if not self._options.no_calculate_volume:
            self._volume = self._calculate_volume()
        else:
            self._volume = None

        if not self._options.no_fetch_subtitles:
            self._fetch_subtitles()

        if self._options.no_play:
            return 0

        cleanup = []

        try:

            if self._options.use_nvperf:
                self._nvperf('+')
                cleanup.append(lambda: self._nvperf('-'))

            mp_pid = os.fork()
            if mp_pid == 0:

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
                    dbg_cmd(cmd)

                os.execlp(*cmd)
                sys.exit(1)

            self._input_file = self._get_input_file(mp_pid)
            cleanup.append(lambda: unlink_if_exists(self._input_file))
            __, status = os.waitpid(mp_pid, 0)

            return status >> 8

        except KeyboardInterrupt:
            pass

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
            dbg_cmd(cmd)

        with open(input_file, 'w') as fp:
            fp.write(cmd + '\n')

        return 0

Player._klasses['dummy'] = Player


class MPV(Player):

    _commands = {
        'pause': 'set pause yes',
        'resume': 'set pause no',
        'show-progress': 'show_progress',
    }

    def _get_play_cmd(self):
        cmd = ['mpv']
        if self._options.profile is not None:
            cmd.append('--profile=%s' % self._options.profile)
        if not sys.stdout.isatty():
            cmd.append('--msg-level=cache=warn:statusline=warn')
        if self._options.verbose:
            cmd.append('-v')
        if self._volume is not None:
            cmd.append('--volume=%u' % self._volume)
        cmd.append('--input-file=%s' % self._input_file)
        return cmd

    def _get_control_cmd(self):
        return self._commands[self._options.cmd]

Player._klasses['mpv'] = MPV


class MPlayer(Player):

    _commands = {
        'pause': 'pausing_keep_force pause',
        'resume': 'seek +0',
        'show-progress': 'osd_show_progression',
    }

    def _get_play_cmd(self):
        cmd = ['mplayer']
        if self._options.profile is not None:
            cmd.extend(['-profile', self._options.profile])
        if not sys.stdout.isatty():
            cmd.extend(['-msglevel', 'cache=3:statusline=3'])
        if self._options.verbose:
            cmd.append('-v')
        if self._volume is not None:
            cmd.append('-volume=%u' % self._volume)
        cmd.extend(['-input', 'file=%s' % self._input_file])
        return cmd

    def _get_control_cmd(self):
        return self._commands[self._options.cmd]

Player._klasses['mplayer'] = MPlayer


parser = argparse.ArgumentParser(prog=MP_PROG)

parser.add_argument('-d', '--debug',
                    action='store_true', default=False,
                    help='enable debug traces')

if MP_PROG == 'mp-play':

    parser.add_argument('-p', '--player',
                        choices=list(Player._klasses.keys()), default='mpv',
                        help='select player to use')
    parser.add_argument('--fetch-subtitles',
                        metavar='LOCATION', action='append', default=[],
                        help='automatically fetch subtitles for files in the specified location')
    parser.add_argument('--no-fetch-subtitles',
                        action='store_true', default=False,
                        help='disable automatically fetching subtitles')
    parser.add_argument('--no-calculate-volume',
                        action='store_true', default=False,
                        help='disable appropriate volume calculation')
    parser.add_argument('--no-play',
                        action='store_true', default=False,
                        help='do not play video')
    parser.add_argument('--subtitles-language',
                        metavar='LANGUAGE', default='en',
                        help='language to use when fetching subtitles')
    parser.add_argument('--use-nvperf',
                        action='store_true', default=False,
                        help='use nvperf to switch to maximum performance during play')
    parser.add_argument('--option',
                        metavar='OPTION', action='append', dest='player_options',
                        help='add an option to be passed to the underlying player')
    parser.add_argument('--profile',
                        help='select the specified configuration profile')
    parser.add_argument('-v', '--verbose',
                        action='store_true', default=False,
                        help='enable verbose mode')

    parser.add_argument('files', nargs='+')

elif MP_PROG == 'mp-control':

    parser.add_argument('pid', type=int, help='PID of the player to control')
    parser.add_argument('cmd', choices=['pause', 'resume', 'show-progress'],
                        help='command to send to player')

else:
    print('invalid mode: %s' % MP_PROG, file=sys.stderr)
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
                for opt_val in shlex.split(v, comments=True):
                    args.append('%s=%s' % (opt_name, opt_val))

args.extend(sys.argv[1:])

options = parser.parse_args(args)

if options.debug:
    dbg('args', args)
    dbg('options', options)

if MP_PROG == 'mp-play':
    player = Player.from_name(options.player, options)
    ret = player.play()
elif MP_PROG == 'mp-control':
    player = Player.from_pid(options.pid, options)
    ret = player.control()

sys.exit(ret)
