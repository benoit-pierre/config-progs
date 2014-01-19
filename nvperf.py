#!/usr/bin/env python2


import fcntl
import os


NVPERF_FILE = '/tmp/nvperf'
NVPERF_LEVELS = [ 'adaptive', 'maximum' ]


def nvperf(mode, verbose=False):

    state_file = open(NVPERF_FILE, 'a+')
    fcntl.flock(state_file, fcntl.LOCK_EX)

    try:

        counter = int('0' + state_file.read())

        if mode in ('?', 'query', None):
            if 0 == counter:
                level = NVPERF_LEVELS[0]
            else:
                level = NVPERF_LEVELS[1]
            print level
            return

        if mode in ('-', 'off', 'adapt'):
            new_counter = counter - 1
        elif mode in ('+', 'on', 'max'):
            new_counter = counter + 1
        else:
            return

        if new_counter < 0:
            new_counter = 0

        if new_counter == counter:
            # No change in level needed
            return

        if 1 == new_counter and 0 == counter:
            # Switch to maximum level.
            new_level = 1
        elif 0 == new_counter:
            # Switch to adaptive level.
            new_level = 0
        else:
            # Already at maximum level.
            new_level = None

        if new_level is not None:

            if verbose:
                level = NVPERF_LEVELS[new_level]
                print 'switching powermizer performance level to %s' % level

            os.system('nvidia-settings -a GPUPowerMizerMode=%u >/dev/null' % new_level)

        os.ftruncate(state_file.fileno(), 0)
        state_file.write('%u' % new_counter)

    finally:

        fcntl.flock(state_file, fcntl.LOCK_UN)
        state_file.close()


if '__main__' == __name__:

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('mode', nargs='?',
                        default='query',
                        choices=['?', 'query', '-', 'off', 'adapt', '+', 'on', 'max'],
                        help='query or set powermizer performance level')
    parser.add_argument('-v', '--verbose',
                        action='store_true', default=False,
                        help='enable verbose mode')

    options = parser.parse_args()

    nvperf(options.mode, verbose=options.verbose)

