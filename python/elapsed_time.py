'''
    Log elapsed time for an activity.

    Copyright 2009-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.

    Consider moving these classes to times module.
'''

import human_readable
from solidlibs.python.times import now

class ElapsedTime():
    ''' Context manager to compute elapsed time.

        >>> from time import sleep
        >>> from solidlibs.python.times import timedelta
        >>> ms = 200
        >>> with ElapsedTime() as et:
        ...     sleep(float(ms)/1000)
        >>> delta = et.timedelta()
        >>> lower_limit = timedelta(milliseconds=ms)
        >>> upper_limit = timedelta(milliseconds=ms+1)
        >>> assert delta > lower_limit
        >>> assert delta <= upper_limit
    '''

    def __init__(self):
        self.start = now()
        self.end = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.end = now()

    def __str__(self):
        return human_readable.precise_delta(self.timedelta())

    def timedelta(self):
        ''' Elapsed time as timedelta type.

            If still in block, then elapsed time so far. '''

        if self.end:
            result = self.end - self.start
        else:
            result = now() - self.start
        return result

class LogElapsedTime():
    ''' Context manager to log elapsed time.

        >>> from time import sleep
        >>> from solidlibs.python.log import Log
        >>> log = Log()
        >>> ms = 200
        >>> with LogElapsedTime(log, 'test sleep'):
        ...     sleep(float(ms)/1000)
    '''

    def __init__(self, log, msg=None):

        # verify 'log' is a log
        if not hasattr(log, 'debug'):
            raise ValueError(f"'log' must be a log, not {type(log)}")

        self.start = now()
        self.log = log
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        elapsed = now() - self.start
        if self.msg:
            self.log.debug(f'{self.msg} elapsed time {elapsed}')
        else:
            self.log.debug(f'elapsed time {elapsed}')


if __name__ == "__main__":
    import doctest
    doctest.testmod()
