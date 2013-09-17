#! /usr/bin/env python2


import traceback
import argparse
import readline
import inspect
import termios
import string
import shutil
import shlex
import stat
import tty
import cmd
import sys
import os


SCRIPT_DIR = os.path.expanduser('~/progs/bin')
WINE_DIR = os.path.expanduser('~/progs/wine')
VERSION_DIR = os.path.join(WINE_DIR, 'version')
PREFIX_DIR = os.path.expanduser('~/progs/games')


def getchar():
    fd = sys.stdin.fileno()
    settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, settings)
    return ch

def ask_yes_no(question=None):
    if question is not None:
        sys.stdout.write(question)
        sys.stdout.flush()
    if 'y' == getchar().lower():
        sys.stdout.write('yes\n')
        return True
    sys.stdout.write('no\n')
    return False


class Wine:

    SETTINGS = (
            ('arch', 'WINEARCH', 'win32'),
            ('debug', 'WINEDEBUG', '-all'),
            ('prefix', 'WINEPREFIX', os.path.expanduser('~/.wine')),
            ('version', None, 'system'),
    )

    TOOLS = [
        'msiexec',
        'notepad',
        'regedit',
        'regsvr32',
        'widl',
        'wine',
        'wineboot',
        'winebuild',
        'winecfg',
        'wineconsole',
        'winecpp',
        'winedbg',
        'winedump',
        'winefile',
        'wineg++',
        'winegcc',
        'winemaker',
        'winemine',
        'winepath',
        'wine-preloader',
        'wineserver',
        'wmc',
        'wrc',
    ]

    def __init__(self):
        self._settings = {}
        for name, env, default in self.SETTINGS:
            if env:
                value = os.environ.get(env, default)
            else:
                value = default
            self._settings[name] = value

    def __str__(self):
        settings = []
        for name, env, default in self.SETTINGS:
            value = self._settings[name]
            settings.append('%s=%s' % (name, value))
        return 'Wine(' + ', '.join(settings) + ')'

    def set(self, setting, value=None):
        if not setting in self._settings:
            raise KeyError
        self._settings[setting] = value

    def get(self, setting, value=None):
        if value is None:
            return self._settings[setting]
        return self._settings.get(setting, value)

    def get_dir(self, subdir=None):
        components = []
        prefix = self._settings['prefix']
        if '/' != dir:
            components.append(PREFIX_DIR)
        components.append(prefix)
        components.append('drive_c')
        if subdir is not None:
            components.append(subdir)
        return os.path.join(*components)

    def execute(self, cmd, args=[], env=None):

        environ = {}

        arch = self._settings['arch']
        prefix = self._settings['prefix']
        if '/' != prefix:
            prefix = os.path.join(PREFIX_DIR, prefix)
        debug = self._settings['debug']
        version = self._settings['version']
        base_dir = os.path.join(VERSION_DIR, version, 'usr')
        bin_dir = os.path.join(base_dir, 'bin')
        lib_dir = os.path.join(base_dir, 'lib')

        environ['WINEARCH'] = arch
        environ['WINEPREFIX'] = prefix
        environ['WINESERVER'] = os.path.join(bin_dir, 'wineserver')
        environ['WINELOADER'] = os.path.join(bin_dir, 'wine')

        if debug is not None:
            environ['WINEDEBUG'] = debug

        path = '%s:%s' % (bin_dir, os.environ['PATH'])

        if 'LD_LIBRARY_PATH' in os.environ:
            ld_library_path = '%s:%s' % (lib_dir, os.environ.get('LD_LIBRARY_PATH'))
        else:
            ld_library_path = lib_dir

        environ['PATH'] = path
        environ['LD_LIBRARY_PATH'] = ld_library_path

        if env is not None:
            environ.update(env)

        if cmd in self.TOOLS:
            cmd = os.path.join(bin_dir, cmd)

        command = [ cmd ]
        command.extend(args)

        print ' '.join(command)

        pid = os.fork()
        if 0 != pid:
            pid, status = os.waitpid(pid, 0)
            return status >> 8

        os.environ.update(environ)
        os.execlp(command[0], *command)
        sys.exit(255)


class ParseError(Exception):
    pass

class ParseEOF(Exception):
    pass


class Whelp:

    class _CommandLine(cmd.Cmd):

        def __init__(self, whelp):
            cmd.Cmd.__init__(self)
            self.prompt = 'whelp> '
            self._whelp = whelp

        def default(self, line):
            args = shlex.split(line, comments=True)
            if 0 == len(args):
                return
            cmd_name, args = args[0], args[1:]
            cmd_fn = getattr(self._whelp, 'cmd_' + cmd_name, None)
            if cmd_fn is None:
                raise ParseError('unknown command: %s' % cmd_name)
            cmd_args, cmd_varargs, _, cmd_defaults = inspect.getargspec(cmd_fn)
            cmd_args.pop(0)
            if cmd_defaults is None:
                cmd_defaults = ()
            if len(args) < len(cmd_args) - len(cmd_defaults):
                raise ParseError('not enough argument(s) for command %s: %s' % (cmd_name, args))
            if len(args) > len(cmd_args) and cmd_varargs is None:
                raise ParseError('too many argument(s) for command %s: %s' % (cmd_name, args))
            cmd_fn(*args)

        def emptyline(self):
            pass

        def _print_cmd_help(self, cmd_name, short=False, align=0):
            cmd_fn = getattr(self._whelp, 'cmd_' + cmd_name, None)
            if cmd_fn is None:
                raise ParseError('unknown command: %s' % cmd_name)
            cmd_help = cmd_fn.__doc__.strip()
            if short:
                cmd_help = cmd_help.split('\n')[0]
            print cmd_help

        def do_help(self, topic):
            topic = topic.strip()
            if '' == topic:
                commands = []
                for attr in dir(self._whelp):
                    if attr.startswith('cmd_') and 'cmd_EOF' != attr:
                        commands.append(attr[4:])
                align = max([len(cmd_name) for cmd_name in commands])
                print 'Available commands:\n'
                for cmd_name in commands:
                    print '%*s :' % (-align, cmd_name),
                    self._print_cmd_help(cmd_name, short=True)
            else:
                self._print_cmd_help(topic)


    def __init__(self):

        self._wine = Wine()
        self._environ = {}
        self._dir = None
        self._dry_run = False

        # Don't isolate winetricks installations in their own prefix.
        self._environ['WINETRICKS_OPT_SHAREDPREFIX'] = '1'

        parser = argparse.ArgumentParser(prog='whelp', add_help=False)

        # Global options.
        parser.add_argument('-i', '--interactive',
                            action='store_true', default=False,
                            help='start interactive command loop')
        parser.add_argument('-s', '--shell',
                            action='store_true', default=False,
                            help='start a shell in the prefix')
        parser.add_argument('-k', '--kill',
                            action='store_true', default=False,
                            help='kill wineserver')
        parser.add_argument('-e', '--execute',
                            nargs=argparse.REMAINDER,
                            help='execute following arguments as command')
        parser.add_argument('-h', '--help',
                            action='store_true', default=False,
                            help='show this help message and exit')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('script', nargs='?')
        group.add_argument('-c', '--create',
                           nargs=argparse.REMAINDER,
                           help='create and setup a new wine prefix')

        self._parser = parser

        # Create options.
        parser_create = argparse.ArgumentParser(prog='',
                                                add_help=False)
        parser_create.add_argument('-n', '--name',
                                   required=True,
                                   help='name of the new prefix')
        parser_create.add_argument('-a', '--arch',
                                   choices=['win32', 'win64'], default='win32',
                                   help='architecture of the new prefix')
        parser_create.add_argument('-v', '--version',
                                   default='system',
                                   help='version of wine to use')
        parser_create.add_argument('-d', '--directx',
                                   action='store_true', default=False,
                                   help='install directx')
        parser_create.add_argument('-s', '--steam',
                                   action='store_true', default=False,
                                   help='install steam')

        self._parser_create = parser_create

        help_create = self.cmd_create.__func__.__doc__
        help_create += '\n\n'
        help_create += parser_create.format_help()
        self.cmd_create.__func__.__doc__ = help_create

    def run(self, *args):

        try:
            options = self._parser.parse_args()
        except SystemExit, e:
            return e.code

        if options.help:
            self._parser.print_help()
            print '\ncreate ',
            self._parser_create.print_help()
            return 0

        if options.create is not None:
            print options.create
            try:
                self.cmd_create(*options.create)
            except Exception, e:
                print >>sys.stderr, e
                return 1
            except SystemExit, e:
                return e.code

        cmdline = self._CommandLine(self)

        if options.script is None:
            if not options.shell:
                options.interactive = True
        else:
            if options.kill or \
               options.shell or \
               options.execute or \
               options.interactive:
                self._dry_run = True

            for line in open(options.script):
                try:
                    cmdline.onecmd(line)
                except ParseEOF:
                    break
                except Exception, e:
                    print >>sys.stderr, e
                    return 1
                except SystemExit, e:
                    return e.code

        self._dry_run = False

        cmd = None

        if options.kill:
            cmd = ('wineserver', '-k')

        if options.execute:
            cmd = options.execute

        if cmd is not None:
            try:
                self.cmd_exec(cmd[0], *cmd[1:])
            except Exception, e:
                print >>sys.stderr, e
                return 1
            except SystemExit, e:
                return e.code

        if options.interactive:
            while True:
                try:
                    cmdline.cmdloop()
                except ParseEOF:
                    break
                except Exception, e:
                    print >>sys.stderr, e
                    pass
                except SystemExit, e:
                    pass
                except KeyboardInterrupt:
                    print
                    pass

        if options.shell:
            self.cmd_shell()

        return 0

    def cmd_exit(self):
        ''' Quit, what else? '''
        print
        raise ParseEOF()

    def cmd_EOF(self):
        self.cmd_exit()

    def cmd_set(self, name, value=None):
        ''' Set or clear a wine setting. '''
        print 'set', name, value
        try:
            self._wine.set(name, value)
        except KeyError:
            raise ParseError('invalid setting: %s' % name)

    def cmd_setenv(self, name, value=None):
        ''' Set or clear an environment variable. '''
        print 'setenv', name, value
        if value is None:
            del self._environ[name]
        else:
            self._environ[name] = value

    def cmd_print(self):
        ''' Show wine settings and environment variables. '''
        max_name = 0
        settings = []
        for name, _, _ in Wine.SETTINGS:
            value = self._wine.get(name)
            name = 'wine.' + name
            if len(name) > max_name:
                max_name = len(name)
            settings.append((name, value))
        for name, value in self._environ.iteritems():
            name = 'env.' + name
            if len(name) > max_name:
                max_name = len(name)
            settings.append((name, value))
        for name, value in settings:
            print '%*s: %s' % (-max_name, name, value)

    def cmd_cd(self, dir=None):
        ''' Change directory (relative to current prefix if not absolute). '''
        self._dir = self._wine.get_dir(dir)
        if self._dry_run:
            return
        print 'cd', self._dir
        os.chdir(self._dir)

    def cmd_exec(self, cmd, *args):
        ''' Execute a command. '''
        if self._dry_run:
            return
        self.cmd_cd(self._dir)
        ext = os.path.splitext(cmd)[1]
        if ext is not None and '.exe' == ext.lower():
            args = [cmd] + list(args)
            cmd = 'wine'
        print 'exec', cmd, ' '.join(args)
        self._wine.execute(cmd, args, env=self._environ)

    def cmd_shell(self):
        ''' Start an interactive shell. '''
        if self._dry_run:
            return
        self.cmd_cd(self._dir)
        shell = os.environ.get('SHELL', '/bin/sh')
        self._wine.execute(shell, env=self._environ)

    def cmd_nvperf(self, mode='query'):
        ''' Query or set NVidia powermizer performance level. '''
        if self._dry_run:
            return
        from nvperf import nvperf
        print 'nvperf', mode
        nvperf(mode, verbose=True)

    def cmd_create(self, *args):

        ''' Create and setup a new wine prefix. '''

        if self._dry_run:
            return

        print 'create', ' '.join(args)

        options = self._parser_create.parse_args(args)

        self.cmd_set('arch', options.arch)
        self.cmd_set('prefix', options.name)
        self.cmd_set('version', options.version)
        self.cmd_print()

        script_path = os.path.join(SCRIPT_DIR, options.name)

        script_template = '''\
#! /usr/bin/env whelp

set arch $arch
set prefix $prefix
set version $version
print
'''
        if options.steam:
            script_template += '''\
exec 'Program Files/Steam/steam.exe' # -applaunch 0000
'''
        script_content = string.Template(script_template)
        script_content = script_content.substitute(
            arch=options.arch,
            prefix=options.name,
            version=options.version,
        )

        if not os.path.exists(script_path) or \
           ask_yes_no('overwrite existing script %s? ' % script_path):
            with open(script_path, 'w+') as script:
                script.write(script_content)
                os.fchmod(script.fileno(), stat.S_IRWXU)

        prefix_path = options.name
        if '/' != prefix_path:
            prefix_path = os.path.join(PREFIX_DIR, prefix_path)
        if os.path.exists(prefix_path) and not \
           ask_yes_no('overwrite existing prefix %s? ' % prefix_path):
            return

        if os.path.exists(prefix_path):
            shutil.rmtree(prefix_path)

        old_dir = self._dir
        self.cmd_cd(PREFIX_DIR)

        reg_defaults = os.path.join(WINE_DIR, 'defaults.reg')
        if os.path.exists(reg_defaults):
            self.cmd_exec('regedit', reg_defaults)

        if options.steam:
            reg_steam = os.path.join(WINE_DIR, 'steam.reg')
            if os.path.exists(reg_steam):
                self.cmd_exec('regedit', reg_steam)

        tricks = ['gecko', 'nocrashdialog']
        if options.directx:
            tricks.extend(['d3dx9', 'd3dcompiler_43'])
        if options.steam:
            tricks.append('steam')
        self.cmd_exec('winetricks', '--unattended', *tricks)
        self.cmd_exec('wineserver', '--wait')

        self._dir = old_dir


if __name__ == '__main__':

    whelp = Whelp()
    ret = whelp.run(*sys.argv[1:])
    sys.exit(ret)

