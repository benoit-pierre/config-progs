#!/usr/bin/env python3


import fcntl
import os
import subprocess


NVPERF_FILE = '/tmp/nvperf'
NVPERF_LEVELS = ['adaptive', 'maximum']


def nvperf(mode, verbose=False):

    state_file = os.fdopen(os.open(NVPERF_FILE, os.O_RDWR | os.O_CREAT), 'rb+')
    fcntl.flock(state_file, fcntl.LOCK_EX)

    try:

        counter = int(b'0' + state_file.read())

        if mode in ('?', 'query', None):
            if counter == 0:
                level = NVPERF_LEVELS[0]
            else:
                level = NVPERF_LEVELS[1]
            print(level)
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

        if new_counter == 1 and counter == 0:
            # Switch to maximum level.
            new_level = 1
        elif new_counter == 0:
            # Switch to adaptive level.
            new_level = 0
        else:
            # Already at maximum level.
            new_level = None

        if new_level is not None:

            if verbose:
                level = NVPERF_LEVELS[new_level]
                print('switching powermizer performance level to %s' % level)

            subprocess.check_call(('nvidia-settings', '-a', 'GPUPowerMizerMode=%u' % new_level))

        state_file.seek(0)
        state_file.write(b'%u' % new_counter)
        os.truncate(state_file.fileno(), state_file.tell())

    finally:

        fcntl.flock(state_file, fcntl.LOCK_UN)
        state_file.close()


if __name__ == '__main__':

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
