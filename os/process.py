'''
    Processes.

    We prefer to use command line programs over python standard modules
    because linux command line programs are more likely to have been
    thoroughly vetted.

    Copyright 2013-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import datetime
import os
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from traceback import format_exc

from solidlibs.os.command import run
from solidlibs.os.user import require_user
from solidlibs.python.log import Log
from solidlibs.python.utils import version
from solidlibs.python.times import now

if version < 3:
    sys.exit('requires python 3 or later')

log = Log()
DEBUGGING = False


class TimedOutException(Exception):
    ''' Operation timed out exception. '''


class CallException(Exception):
    ''' call() exception. '''


def pid_from_port(port):
    ''' Find which pid opened the port.

        This can be much faster than trying to connect to a port.
        Calling socket.socket().connect() sometimes succeeds for every port.

        Returns None if none.

        >>> from solidlibs.os.user import whoami
        >>> if whoami == 'root':
        ...     pids = pid_from_port(9988)
        ...     pids is None
        ... else: print(True)
        True
    '''

    # fuser requires --namespace before port, so can't use namespace='tcp'
    pids = pids_from_fuser('--namespace', 'tcp', port)
    if pids:
        assert len(pids) == 1, f'pids: {pids}'
        pid = pids[0]
        result = int(pid)
    else:
        result = None
    return result

def pids_from_file(path):
    ''' Get list of pids that have the file or dir open.

        Returns an empty list if no pids.

        >>> from solidlibs.os.user import whoami
        >>> if whoami == 'root':
        ...     pids = pids_from_file('/tmp')
        ...     len(pids) == 0
        ... else: print(True)
        True
    '''

    return pids_from_fuser(path)

def pids_from_program(program):
    ''' Get list of pids for program.

        Returns empty list if none

        >>> from solidlibs.os.user import whoami
        >>> if whoami == 'root':
        ...     pids = pids_from_program('python3')
        ...     len(pids) > 0
        ... else: print(True)
        True
    '''

    try:
        pid_strings = run('pidof', program).stdout.strip().split()
    except subprocess.CalledProcessError:
        pids = []
    else:
        pids = [int(pid) for pid in pid_strings]

    return pids

def program_from_pid(pid):
    ''' Find which program has the pid.

        The program is the full path of the running program. This may
        not match the program on the command line, if the program on
        the command line is a link.

        Returns None if none.

        >>> program = program_from_pid(9988)
        >>> program is None
        True
    '''

    # /proc/PID/exe is a link to the program
    try:
        program = os.readlink(f'/proc/{pid}/exe')
    except OSError:
        program = None

    log.debug(f'program_from_pid({pid}): {program}')
    return program

def program_from_port(port):
    ''' Find which program opened the port.

        See program_from_pid(pid).

        Returns None if none.

        >>> from solidlibs.os.user import whoami
        >>> if whoami == 'root':
        ...     pid = program_from_port(9988)
        ...     pid is None
        ... else: print(True)
        True
    '''

    log.debug(f'port: {port}')
    pid = pid_from_port(port)
    log.debug(f'pid: {pid}')
    if pid:
        program = program_from_pid(pid)
    else:
        program = None

    return program

def programs_using_file(path):
    ''' Find which programs have the file or dir open.

        Returns None if none.

        >>> from solidlibs.os.user import whoami
        >>> if whoami == 'root':
        ...     programs = programs_using_file('/tmp')
        ...     programs is None
        ... else: print(False)
        False
    '''

    programs = set()

    # fuser
    pids = pids_from_file(path)
    if pids:
        log.debug(f'pids using {path}: {pids}')

        for pid in pids:
            program = program_from_pid(pid)
            if program:
                programs.add(program)
            else:
                log.debug(f'no program from pid  {pid}')

    # lsof
    lines = run('lsof').stdout.strip().split('\n')
    for line in lines:
        fields = line.split()
        command = fields[0]
        command_path = fields[-1]
        if command_path == path or command_path.startswith(path + '/'):
            programs.add(command)

    if programs:
        programs = sorted(programs)
    else:
        programs = None

    return programs

def pids_from_fuser(*args):
    ''' Get list of pids using fuser.

        Returns Empty list if no pids.

        Example:
                # fuser --namespace tcp 9050
                9050/tcp:             3331

            WARNING: Very strangely, fuser sends the first part of the line to
            stderr, and the second part to stdout. The stdout splits on the
            spaces.

            fuser also returns an exit code of 1.

        >>> from solidlibs.os.user import whoami
        >>> if whoami == 'root':
        ...     pids = pids_from_fuser(*['--namespace', 'tcp', '9988'])
        ...     len(pids) == 0
        ... else: print(True)
        True
    '''

    require_user('root') # fuser requires root

    log.debug(f'pids_from_fuser(*args) args: {repr(args)}')
    try:
        fuser_out = run('fuser', *args, _ok_code=[0, 1])
    except:   # noqa
        # log.debug(format_exc()) # DEBUG
        pids = []
    else:
        log.debug(f'pids_from_fuser() fuser_out: {repr(fuser_out)}')
        # only the pids g to stdout
        pid_strings = fuser_out.stdout.strip().split()
        pids = [int(pid) for pid in pid_strings]

    log.debug(f'pids_from_fuser() pid: {pids}')

    return pids

def is_program_running(program_name):
    '''
        Return True if program is running and not defunct.

        See find_active_program() for details on program_name.

        >>> is_program_running('python3')
        True
        >>> is_program_running('not.running')
        False
    '''

    return find_active_program(program_name) is not None

def get_pid(program_name):
    '''
        Return first matching pid if program is running and not defunct.

        See find_active_program() for details on program_name.

        >>> pid = get_pid('python3')
        >>> pid is not None
        True
        >>> type(pid)
        <class 'int'>
    '''

    pid = None

    line = find_active_program(program_name)
    if line is not None:
        index = line.find(' ')
        if index > 0:
            pid = int(line[:index])

    return pid

def wait_for_children():
    ''' Wait for all children processes to finish.

        >>> from solidlibs.os.command import background
        >>> for secs in range(3):
        ...     process = background('sleep', secs)
        >>> wait_for_children()
    '''

    while wait_any_child():
        time.sleep(0.1)

def wait_any_child():
    ''' Wait for any child process to finish.

        Returns:
            (pid, signal, exit_code)

            pid: the process id
            signal: the signal number that killed the process, or zero
            exit_code: the process exit code

        >>> from solidlibs.os.command import background
        >>> pids = []
        >>> for secs in range(3):
        ...     process = background('sleep', secs)
        ...     pids.append(process.pid)

        >>> done = False
        >>> while not done:
        ...     child = wait_any_child()
        ...     if child:
        ...         pid, signal, exit_code = child
        ...         assert pid != 0
        ...         assert signal == 0
        ...         assert exit_code == 0
        ...     else:
        ...         done = True
    '''

    ANY_CHILD_PID = -1 # any child of this process
    OPTIONS = 0 # os.WEXITED | os.WSTOPPED

    try:
        result = decode_wait_result(os.waitpid(ANY_CHILD_PID, OPTIONS))

    except ChildProcessError:
        result = None

    return result

def decode_wait_result(result):
    ''' Decode result from os.waitpid() etc. '''

    pid, exit_status = result
    signal = (exit_status >> 8) & 0xFF
    exit_code = exit_status & 0xFF

    return pid, signal, exit_code


def child_pids():
    ''' Return all child pids. '''

    # verbose(f'in child_pids() os.getpid(): {os.getpid()}') # DEBUG
    result = run('pgrep', '--parent', os.getpid())
    candidate_pids = list(map(int, result.stdout.split()))
    # verbose(f'in child_pids() candidate_pids: {candidate_pids}') # DEBUG
    # remove zombies
    pids = []
    for pid in candidate_pids:
        if is_pid_active(pid):
            pids.append(pid)
    # verbose(f'in child_pids() pids: {pids}') # DEBUG

    return pids

def get_path(program_name):
    '''
        Return first matching path if program is running and not defunct.

        See find_active_program() for details on program_name.

        >>> TARGET = 'python3'
        >>> path = get_path(TARGET)
        >>> path is not None
        True
        >>> type(path)
        <class 'str'>
    '''

    path = None

    line = find_active_program(program_name)
    if line is not None:
        parts = line.split()
        if len(parts) > 1:
            path = parts[1]

    return path

def find_active_program(program_name):
    '''
        Return the first matching raw line from "ps" if program is running.
        Ignores any program_name that is defunct.

        The program name must match the running program exactly.
        If program_name includes a directory, it must match.
        If the directory varies, you may want to pass just the
        basename of the program.

        >>> line = find_active_program('python3')
        >>> line is not None
        True
    '''

    raw_line = None

    try:
        raw_lines = program_status(program_name)
        if raw_lines:
            raw_line = raw_lines[0]
    except:   # noqa
        log(format_exc())
        raw_line = None

    return raw_line


def program_status(program_name):
    '''
        Returns a list of matching raw lines from "ps" if program is running.
        If no lines match, returns an empty list.
        Ignores any program_name that is defunct.

        >>> lines = program_status('python3')
        >>> lines == []
        False
    '''
    PS_ARGS = ['-eo', 'pid,args']

    lines = []
    try:
        raw = run('ps', *PS_ARGS)
        raw_lines = raw.stdout.strip().split('\n')

        for line in raw_lines:
            line = str(line).strip()
            # apparent the leading space matters
            if program_name in line and ' <defunct>' not in line:
                lines.append(line)
    except:   # noqa
        log(format_exc())

    return lines

def wait(event, timeout=None, sleep_time=1, event_args=None, event_kwargs=None):
    ''' Wait for an event. Retries event until success or timeout.

        Default is to ignore exceptions except when there is a timeout.

        'event' is a function. event() succeeds if it does not raise an
        exception. Each call to event() continues until it succeeds or
        raises an exception. It is not interrupted if it times out.

        'timeout' can be in seconds as an int or float, or a
        datetime.timedelta, or a datetime.datetime. Default is None, which
        means no timeout. If the timeout deadline passes while event() is
        running, event() is not interrupted. If event() times out while
        running and does not succeed, wait() raises the exception from event().

        'sleep_time' is in seconds. Default is one.

        'event_args' is an list of positional args to event(). Default is None.
        'event_kwargs' is an dict of keyword args to event(). Default is None.

        Returns result from event() if no timeout, or if timeout returns last exception.
    '''

    def timed_out():
        return timeout and (now() >= deadline)

    if timeout:

        if isinstance(timeout, int or float):
            deadline = now() + datetime.timedelta(seconds=timeout)

        elif isinstance(timeout, datetime.timedelta):
            deadline = now() + timeout

        elif isinstance(timeout, datetime.datetime):
            deadline = timeout

        else:
            raise TypeError('timeout must be an int, float, datetime.timedelta, or datetime.datetime')

        log.debug(f'wait() timeout: {timeout}, deadline: {deadline}')

    if event_args is None:
        event_args = []
    if event_kwargs is None:
        event_kwargs = {}

    success = False
    while not success:
        try:
            result = event(*event_args, **event_kwargs)

        except KeyboardInterrupt:
            raise

        except:   # noqa
            if timed_out():
                log.debug(f'wait() timed out with exception: {format_exc()}')
                raise
            log.debug(f'wait() ignored exception because not timed out:\n{format_exc()}')

        else:
            success = True

        if not timed_out():
            time.sleep(sleep_time)

    return result

@contextmanager
def fork_child():
    ''' Context manager to run a forked child process.

        Subprocess returns a process result code of 0 on success,
        or -1 if the child block raises an exception.

        Including "if os.fork() == 0:" in the context manager results in::

        RuntimeError: generator didn't yield

        >>> parent_pid = os.getpid()
        >>> # if child process
        >>> if os.fork() == 0:
        ...     with fork_child():
        ...         # child process code goes here
        ...         assert parent_pid != os.getpid()
        >>> assert parent_pid == os.getpid()
    '''

    return_code = 0

    # try to run in a new session
    try:
        os.setsid()
    except:   # noqa
        pass

    # continue after the calling process ends
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    try:
        yield
    except:   # noqa
        return_code = -1
    finally:
        os._exit(return_code)

def zombies():
    ''' Return list of zombies in the format::

            [(pid, parent_pid), ...]

        Sometimes when you stop a process, a zombie process lives.
        A process becomes a zombie when the process finishes running, but
        the parent process didn't wait for it. The fix is to make the
        parent wait for the subprocess. A workaround is to kill the parent
        process.
    '''

    pids = []

    stdout = run('ps', '-A', '--format', 'stat,pid,ppid').stdout
    for line in stdout.split('\n'):
        stat, pid, ppid = line.split()
        if 'Z' in stat.upper():
            pids.append((pid, ppid))

    return pids

def kill(pid):
    ''' Kill pid. '''

    # it takes multiple signals to kill reliably
    for sig in [signal.SIGTERM, signal.SIGHUP, signal.SIGKILL]:
        try:
            os.kill(pid, sig)
        except Exception:
            pass

def is_pid_active(pid):
    ''' Return True if pid is active. Else return False.

        >>> is_pid_active(os.getpid())
        True
    '''

    try:
        # this does not "kill" the process,
        # just checks to see if it's alive
        os.kill(pid, 0)
    except OSError:
        active = False
    else:
        active = True

    return active


if __name__ == "__main__":

    import doctest
    doctest.testmod()
