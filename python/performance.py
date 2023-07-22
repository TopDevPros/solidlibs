'''
    Python performance profiler.

    Install:

        pip install solidlibs

    Usage:

        from solidlibs.python.performance import profile

        @profile
        def my_function():
            ...

    How it works:

        To fix a slow program, you have to profile first. If you don't,
        most of your time is wasted on code you don't need to optimize.

        This is like the standard python profilers, but simpler and easier.

        Add the '@profile' decorator to each function you want to profile.

        Run your program. You'll see a report on which functions take
        the most total time and the average run time for each function.

        See exactly where the slowdowns are.

    Optimize where it matters:

        When it's not clear where to start, start in main().

        For each level, instrument the called functions with @profile,
        then continue into the slowest ones.

    Tips:

        To profile part of a function, separate that part into its own
        function.

        If a function decorated with @profile calls another function that
        is also decorated with @profile, the time for the caller function
        includes the called function time. So total times for functions
        can add up to more than the total time for the program.

    Copyright 2022-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

from datetime import timedelta
from functools import wraps
import sys

from solidlibs.python.dict import Simple
from solidlibs.python.elapsed_time import ElapsedTime
from solidlibs.python.internals import caller_module_name
from solidlibs.python.log import Log
from solidlibs.python.times import (now, timestamp, timedelta_to_human_readable,
                                 timedelta_to_seconds)

functions = {}
start = now()

# let other modules set some params
profile_enabled = True
verbose = False

log = Log()

def profile(f):
    ''' Function decorator to profile functions.

        Args:
            f: The function to profile.
    '''

    @wraps(f)

    def measure(*args, **kwargs):
        ''' Profile a function decorated with @profile.

            Args:
                args: the function's positional args.
                kwargs: the function's keyword args.

            Returns:
                The function's return values.
        '''

        if profile_enabled:
            try:
                f.__name__
            except AttributeError:
                # static methods have no __name__
                # see https://stackoverflow.com/questions/41921255/staticmethod-object-is-not-callable
                function = f.__func__
                function_name = function.__name__
            else:
                function = f
                function_name = f.__name__

            f_name = f'{caller_module_name(ignore=[__file__])}.{function_name}'

            if f_name in functions:
                f_data = functions[f_name]
                f_data.count += 1
            else:
                f_data = Simple()
                f_data.name = f_name
                f_data.count = 1
                f_data.calls = []
                f_data.total_time = timedelta()

                functions[f_name] = f_data

            metrics = Simple()

            metrics.start = now()

            # to_stderr(f'Call {f_name}')

            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                to_stderr(exc)
                to_stderr(f'args: {args}')
                to_stderr(f'kwargs: {kwargs}')
                raise

            # if result is None:
            #     to_stderr(f'Called {f_name}')
            # else:
            #     to_stderr(f'Called {f_name}: {result}')

            metrics.end = now()
            metrics.elapsed_time = metrics.end - metrics.start
            f_data.total_time += metrics.elapsed_time

            f_data.calls.append(metrics)

            functions[f_name] = f_data

        else:
            result = f(*args, **kwargs)

        return result

    return measure

def summarize(verbose=verbose):
    ''' Summarize performance results

        Args:
            verbose: If True (False is the default), print a verbose
                summary.
    '''
    def func_total_time(f_name):
        return functions[f_name].total_time

    if profile_enabled:
        to_stderr('Performance summary')
        if functions:
            functions_by_total_time = sorted(functions.keys(),
                                             key=func_total_time,
                                             reverse=True)
            for f_name in functions_by_total_time:
                func = functions[f_name]
                to_stderr(f'    {func.name}')
                to_stderr(f'        calls: {len(func.calls)}')
                if func.calls:
                    total_time = timedelta()
                    for call in func.calls:
                        total_time += func.total_time
                    to_stderr(f'        total elapsed time: {total_time}')
                    if len(func.calls) > 1:
                        to_stderr(f'        average elapsed time: {total_time / len(func.calls)}')

        else:
            to_stderr('    No data')

def to_stderr(msg):
    ''' Print to stderr.

        Args:
            msg: String to print to stderr.
    '''

    print(msg, file=sys.stderr)

@profile
def test():
    ''' Test function for this module. '''

    to_stderr('Running test() function')

import atexit
atexit.register(summarize)


if __name__ == "__main__":
    import doctest
    doctest.testmod()

    # multiple function calls to profile
    test()
    test()
    test()
