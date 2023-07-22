#! /usr/bin/python3
'''
    Python profiling.
    profile_addons is named to avoid conflict with python's profile pacakge.

    This module does not work well with threads. Run a profile inside the thread.
    Remember that profiling slows your code, so remove it when not needed.

    Copyright 2014-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import cProfile
import pstats
import time
from io import StringIO

from solidlibs.python.log import Log

log = Log()

def run(command, datafile, global_vars=None, local_vars=None):
    ''' Profile python code

        'command' is python code as a string

        'datafile' is the pathname to write profile data.

        run() executes the python string in 'command'. Example:
            profile('myprogram.main()', '/tmp/main.profile')
        should be called in place of:
            myprogram.main()

        WARNING: stdout and stderr of the function profiles may go in the bit bucket (why?)
                 If you suspect an error in your code, run it without cProfile.

        >>> import os
        >>>
        >>> DATA = '/tmp/solidlibs.python.profile.data'
        >>>
        >>> if os.path.exists(DATA):
        ...     os.remove(DATA)
        >>> run('_sample_test_code()', DATA, globals(), locals())
        start
        end
        >>> assert os.path.getsize(DATA)
    '''

    log.debug(f'run({repr(command)})')

    if global_vars is None and local_vars is None:
        cProfile.run(command, datafile)
    else:
        cProfile.runctx(command, global_vars, local_vars, filename=datafile, sort=-1)

    log.debug('run() done')

def report(datafile, lines=None):
    ''' Report on profile data from datafile.

        Default lines to print is 20.

        If you need to profile before the program ends, set a timer to
        invoke report().

        Returns report text.

        >>> import os, os.path
        >>>
        >>> DATA = '/tmp/solidlibs.python.profile.data'
        >>> REPORT = '/tmp/solidlibs.python.profile.report'
        >>>
        >>> for path in [DATA, REPORT]:
        ...     if os.path.exists(path):
        ...         os.remove(path)
        >>> run('_sample_test_code()', DATA, globals(), locals())
        start
        end
        >>> text = report(DATA)
        >>> assert text
        >>>
        >>> with open(REPORT, 'w') as f:
        ...     result = f.write(text)
        >>> os.path.getsize(REPORT) > 0
        True
    '''

    if not lines:
        lines = 20

    out = StringIO()
    stats = pstats.Stats(datafile, stream=out)
    # stats.strip_dirs()
    stats.sort_stats('cumulative', 'time', 'calls')
    stats.print_stats(lines)
    text = out.getvalue()

    log.debug(f'report from {datafile}:\n{text}')

    return text

def report_to_file(codestring, reportfile, datafile=None, global_vars=None, local_vars=None):
    ''' Profile codestring and write report to reportfile. '''

    def write_report():
        text = report(datafile)
        with open(reportfile, 'w') as f:
            f.write(text)
        log.debug(f'profile report is in {reportfile}')

    if datafile is None:
        datafile = reportfile + '.data'

    try:
        run(codestring, datafile, global_vars=global_vars, local_vars=local_vars)
    except:   # NOQA
        log.debug('always report profile')
        write_report()
        raise

    else:
        write_report()

def write_report(datafile, reportfile):
    ''' Write report from datafile to reportfile. '''

    text = report(datafile)
    with open(reportfile, 'w') as f:
        f.write(text)
    log.debug(f'profile report is in {reportfile}')

def _sample_test_code():
    ''' Sample code to use for profile testing. '''

    def start():
        print('start')

    def sleep():
        time.sleep(3)

    def end():
        print('end')

    start()
    sleep()
    end()


if __name__ == "__main__":

    import doctest
    doctest.testmod()
