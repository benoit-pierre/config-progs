#! /usr/bin/env python2


import ConfigParser as configparser
import subprocess
import mimetypes
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

    _SUBDOWNLOADERS = (
        'periscope',
        'subberthehut',
        'subdownloader',
    )

    def __init__(self, options):
        self._options = options
        self._dev_null = open('/dev/null', 'w')

    def _get_input_file(self, pid):
        return '%s/input-%u' % (MP_DIR, pid)

    def _get_play_cmd(self):
        return [ 'python2', '-c',
                'import sys; input = open(sys.argv[1], "r+");\nwhile True:\n sys.stdout.write(input.readline())',
                self._input_file ]

    def _nvperf(self, mode):
        from nvperf import nvperf
        if self._options.debug:
            dbg('nvperf', mode)
        nvperf(mode, verbose=self._options.verbose)

    def _is_video(self, file):
        ''' Check if file is a video file. '''
        mimetypes.init()
        type, encoding = mimetypes.guess_type(file)
        if type is None:
            return False
        return type.startswith('video/')

    def _need_subtitles(self, file):
        ''' Do we need subtitles for this file? '''
        directory = os.path.dirname(os.path.realpath(file))
        if '/' != directory[-1]:
            directory += '/'
        for path in self._options.fetch_subtitles:
            if '/' != path[-1]:
                path += '/'
            if directory.startswith(path):
                return True
        return False

    def _has_subtitles(self, file):
        ''' Check if subtitles for the specified file exists. '''
        file_name, file_ext = os.path.splitext(os.path.basename(file))
        for entry in os.listdir(os.path.dirname(os.path.abspath(file))):
            name, ext = os.path.splitext(entry)
            if '.srt' != ext.lower():
                continue
            if name.lower() == file_name.lower():
                return True
        return False

    def _call_subtitles_downloader(self, cmd):
        if self._options.debug:
            dbg('cmd', cmd)
        if self._options.debug:
            stdout = sys.stdout
            stderr = sys.stderr
        else:
            stdout = self._dev_null
            stderr = subprocess.STDOUT
        try:
            return subprocess.call(cmd, stdout=stdout, stderr=stderr)
        except OSError, e:
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
        return 0 == self._call_subtitles_downloader(cmd)

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
        return 0 == self._call_subtitles_downloader(cmd)

    def _fetch_subtitles_subdownloader(self, file):
        cmd = [
            'subdownloader',
            '--lang', self._options.subtitles_language,
            '--video', os.path.abspath(file),
            '--rename-subs',
            '--cli', '-D',
        ]
        if 0 != self._call_subtitles_downloader(cmd):
            return False
        # Need to check ourself if subtitles were found since subdownloader
        # error code does not indicate it.
        return self._has_subtitles(file)

    def _fetch_subtitles(self):

        if 0 == len(self._options.fetch_subtitles):
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

    def play(self):

        self._fetch_subtitles()

        cleanup = []

        try:

            if self._options.use_nvperf:
                self._nvperf('+')
                cleanup.append(lambda: self._nvperf('-'))

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

    parser.add_argument('--fetch-subtitles',
                        metavar='LOCATION', action='append',
                        help='automatically fetch subtitles for files in the specified location')
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

