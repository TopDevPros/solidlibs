'''
    Client side for Multiprocess-safe locks.

    Requirements:
      * The safelock package available on PyPI. It also installs safelog.
      * Running safelock and safelog servers. The servers can be started
        by hand or with the included systemd service file.

    Copyright 2011-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import os
import socket
import threading
from contextlib import contextmanager
from datetime import timedelta
from functools import wraps
from time import sleep
from traceback import format_exc

from solidlibs.python.internals import caller_id
from solidlibs.python.log import Log
from solidlibs.python.times import now
from solidlibs.python.utils import object_name


DEBUGGING = False

# constants shared with solidlibs.python.log and solidlibs.python.logwriter are
# in solidlibs.python.log so they can be imported easily by tools
SAFELOCK_HOST = 'localhost'
SAFELOCK_PORT = 8674
BIND_ADDR = (SAFELOCK_HOST, SAFELOCK_PORT)
MAX_PACKET_SIZE = 1024

ACTION_KEY = 'action'
LOCKNAME_KEY = 'lockname'
NONCE_KEY = 'nonce'
PID_KEY = 'pid'
OK_KEY = 'ok'
MESSAGE_KEY = 'message'
LOCK_ACTION = 'lock'
UNLOCK_ACTION = 'unlock'

REJECTED_LOCK_MESSAGE = 'safelock rejected "{}" lock request: {}'
REJECTED_UNLOCK_MESSAGE = 'safelock rejected "{}" unlock request: {}'
WHY_UNKNOWN = 'safelock did not say why'

DEFAULT_TIMEOUT = timedelta.max

# global variables
log = Log()
# WARNING: BUG. python globals are not multiprocess-safe.
synchronized_locks = {}

class LockTimeout(Exception):
    pass

class LockFailed(Exception):
    pass

@contextmanager
def locked(lockname=None, timeout=None, server_required=True):
    ''' Get a simple reusable lock as a context manager.

        'name' same as lock(). Default is a name created from the
        calling module and line number.

        'timeout' is the maximum time locked() waits for a lock,
        as a  timedelta. Default is one minute.
        If a lock waits longer than 'timeout',
        locked() logs the failure and raises LockTimeout.
        If your locked code block can take longer, you must set
        'timeout' to the longest expected time.

        'server_required' specifies whether the lock server is
        required. If your code must work even when the lock server
        is down, set server_required=False. This should only be
        used for critical code.

        With locked() you don't have to initialize each lock in an
        an outer scope, as you do with raw multiprocessing.Lock().

        The lock returned by locked() is also a context manager. You
        don't have to explicitly call acquire() or release().

        >>> with locked():
        ...     print('this is a locked code block')
        this is a locked code block

        >>> with locked(timeout=1):
        ...     print('this is a locked code block with a timeout')
        ...     sleep(2)
        this is a locked code block with a timeout
        >>> print('after locked code block with a timeout')
        after locked code block with a timeout

        The python standard multiprocessing. Lock won't let you call
        multiprocessing.Lock.release() if the lock is already unlocked. The
        context manager returned by locked() enforces that restriction
        painlessly by calling release() automatically for you.

        If for some reason you use 'with locked()' with no name twice on the
        same line, it will return the same lock twice. You're extremely
        unlikely to do that accidentally.
    '''

    is_locked = False

    try:

        if not lockname:
            lockname = caller_id(ignore=[__file__, r'.*/contextlib.py'])

        is_locked, nonce, pid = lock(lockname, timeout, server_required=server_required)
        if DEBUGGING:
            if is_locked:
                if timeout is None:
                    log(f'{lockname} locked with no timeout')
                else:
                    log(f'{lockname} locked with {timeout} timeout')
            else:
                log(f'unable to get lock for {lockname}')

    except Exception:
        #from solidlibs.python.utils import stacktrace

        log.exception()
        # don't stop if running test_until_exception
        # error_message = stacktrace().replace('Traceback', 'Stacktrace') # but without 'Traceback' # DEBUG
        # log(error_message)
        raise

    else:
        try:
            yield
        finally:
            if is_locked:
                unlock(lockname, nonce, pid, timeout, server_required=server_required)
                if DEBUGGING:
                    log(f'{lockname} unlocked')

def lock(lockname, timeout=None, server_required=True):
    '''
        Lock a process or thread to prevent concurrency issues.

        'lockname' is the name of the lock.

        Every process or thread that calls "lock()" from the
        same source file and line number contends for the same
        lock. If you want many instances of a class to run at
        the same time, each instance's lockname for a particular
        call to lock() must use a different lockname.
        Example::

            lockname = f'MyClass {self.instance_id()}'
            lock(lockname)

        You may still choose to include the source path and line number
        from solidlibs.python.process.caller() in your lockname.

        If for some reason you use 'with locked()' with no name twice on the
        same line, the second 'with locked()' will fail. They both have the
        same default lockname with the same caller and line number. You're
        extremely unlikely to do that accidentally.

        >>> pid = os.getpid()
        >>> log(f'pid: {pid}')

        >>> log('test simple lock()/unlock()')
        >>> from solidlibs.os.process import is_pid_active
        >>> lockname = 'lock1'
        >>> is_locked, nonce, pid = lock(lockname)
        >>> is_locked
        True
        >>> isinstance(nonce, str)
        True
        >>> is_pid_active(pid)
        True
        >>> unlock(lockname, nonce, pid)
        True

        >>> log('test relock')
        >>> lockname = 'lock1'
        >>> is_locked, nonce, __ = lock(lockname)
        >>> is_locked
        True

        >>> log('while locked, try to lock again should fail')
        >>> try:
        ...     lock(lockname, timeout=timedelta(milliseconds=3))
        ... except LockTimeout as lt:
        ...     print(str(lt))
        lock timed out: lock1

        >>> log('now unlock it')
        >>> unlock(lockname, nonce, pid)
        True

        >>> log('try 2 locks')
        >>> lockname1 = 'lock1'
        >>> is_locked1, nonce1, pid1 = lock(lockname1)
        >>> is_locked1
        True
        >>> lockname2 = 'lock2'
        >>> is_locked2, nonce2, pid2 = lock(lockname2)
        >>> is_locked2
        True
        >>> nonce1 != nonce2
        True
        >>> pid1 == pid2
        True
        >>> unlock(lockname1, nonce1, pid1)
        True
        >>> unlock(lockname2, nonce2, pid2)
        True
    '''

    nonce = None
    pid = os.getpid()

    deadline = get_deadline(timeout)
    if DEBUGGING:
        log(f'lock deadline: {deadline}') # DEBUG

    # we can probably factor this out into a general case
    loop_count = 0
    is_locked = False
    last_warning = None
    while not is_locked:
        try:
            is_locked, nonce = try_to_lock(lockname, pid, server_required=server_required)

        except TimeoutError as te:
            log(str(te))

        except LockFailed as lf:
            # we need a better way to handle serious errors
            if 'Wrong nonce' in str(lf):
                raise
            message = lf.args[0]
            if message != last_warning:
                last_warning = message
                log(message)

        except:   # NOQA
            log(format_exc())
            raise

        if not is_locked:
            if deadline and now() > deadline:
                warning_msg = f'lock timed out: {lockname}'
                log.warning(warning_msg)
                raise LockTimeout(warning_msg)

            sleep(0.1)

        loop_count = loop_count + 1

    return is_locked, nonce, pid

def try_to_lock(lockname, pid, server_required=True):
    ''' Try once to lock. '''

    is_locked = False
    nonce = None

    # Create a socket (SOCK_STREAM means a TCP socket)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

        connected = connect_to_server(sock, server_required=server_required)

        if connected:
            # send request
            data = {ACTION_KEY: LOCK_ACTION,
                    LOCKNAME_KEY: lockname,
                    PID_KEY: pid}
            # log(f'about to send lock request: {data}')
            try:
                sock.sendall(repr(data).encode())
                # log('finished sending lock request')

            except BrokenPipeError as bpe:
                log.warning(bpe)
                raise LockFailed('probably safelock server down')

            else:
                # get response
                data = sock.recv(MAX_PACKET_SIZE)
                # log(f'finished receiving lock data: {data}')
                try:
                    response = eval(data.decode())
                except:             # pylint:bare-except -- catches more than "except Exception"
                    log(format_exc())
                    is_locked = False
                else:

                    is_locked = (response[OK_KEY] and
                                 response[ACTION_KEY] == LOCK_ACTION and
                                 response[LOCKNAME_KEY] == lockname)

                    if is_locked:
                        nonce = response[NONCE_KEY]
                        # log(f'locked: {lockname} with {nonce} nonce') # DEBUG
                    else:
                        # if the server responded with 'No'
                        if MESSAGE_KEY in response:
                            message = REJECTED_LOCK_MESSAGE.format(lockname, response[MESSAGE_KEY])
                        else:
                            message = REJECTED_LOCK_MESSAGE.format(lockname, WHY_UNKNOWN)
                        #log(message)
                        raise LockFailed(message)

    return is_locked, nonce

def unlock(lockname, nonce, pid, timeout=None, server_required=True):
    '''
        >>> log('Unlock a process or thread that was previously locked.')
        >>> lockname = 'lock1'
        >>> __, nonce, pid = lock(lockname)
        >>> unlock(lockname, nonce, pid)
        True

        >>> log('A bad nonce should fail.')
        >>> lockname = 'lock1'
        >>> __, nonce, pid = lock(lockname)
        >>> try:
        ...    unlock(lockname, 'bad nonce', pid)
        ...    assert False, 'Unexpectedly passed bad nonce'
        ... except LockFailed:
        ...     pass
        >>> unlock(lockname, nonce, pid)
        True
    '''

    deadline = get_deadline(timeout)
    # log(f'unlock deadline: {deadline}') # DEBUG

    # we must be persistent in case the Safelock is busy
    is_locked = True
    last_warning = None
    while is_locked:
        try:
            is_locked = try_to_unlock(lockname,
                                      nonce,
                                      pid,
                                      server_required=server_required)

        except TimeoutError as te:
            log(str(te))

        except LockFailed as lf:
            # we need a better way to handle serious errors
            if 'Wrong nonce' in str(lf):
                raise
            message = lf.args[0]
            if message != last_warning:
                last_warning = message
                log(message)

        except:   # pylint:bare-except -- catches more than "except Exception"
            log(format_exc())
            raise

        if is_locked:
            if deadline and now() > deadline:
                log.warning(f'unlock timed out: {lockname}')
                raise LockTimeout(warning_msg)

            sleep(0.1)

    # log(f'unlocked: {lockname}') # DEBUG

    # only returned for testing purposes
    return not is_locked

def try_to_unlock(lockname, nonce, pid, server_required=True):
    ''' Try once to unlock. '''

    is_locked = True

    # Create a socket (SOCK_STREAM means a TCP socket)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

        connected = connect_to_server(sock, server_required=server_required)

        if connected:
            # send request
            data = {ACTION_KEY: UNLOCK_ACTION,
                    LOCKNAME_KEY: lockname,
                    NONCE_KEY: nonce,
                    PID_KEY: pid}
            # log(f'about to send unlock request: {data}')

            try:
                sock.sendall(repr(data).encode())
                # log('finished sending unlock request')

            except BrokenPipeError as bpe:
                log.warning(bpe)
                raise LockFailed('probably safelock server down')

            else:

                # get response
                data = sock.recv(MAX_PACKET_SIZE)
                #log(f'finished receiving unlock data: {data}')

                try:
                    response = eval(data.decode())
                except:             # pylint:bare-except -- catches more than "except Exception"
                    log(format_exc())
                    is_locked = False
                else:
                    if response[OK_KEY] and response[ACTION_KEY] == UNLOCK_ACTION and response[NONCE_KEY] == nonce:

                        is_locked = False

                    else:
                        # if the server responded with 'No'
                        if MESSAGE_KEY in response:
                            message = REJECTED_UNLOCK_MESSAGE.format(lockname, response[MESSAGE_KEY])
                        else:
                            message = REJECTED_UNLOCK_MESSAGE.format(lockname, WHY_UNKNOWN)
                        #log(message)
                        raise LockFailed(message)

    return is_locked

def synchronized(function):
    ''' Decorator to lock a function so each call completes before
        another call starts.

        If you use both the staticmethod and synchronized decorators,
        @staticmethod must come before @synchronized.
    '''

    @wraps(function)
    def synchronizer(*args, **kwargs):
        ''' Lock function access so only one call at a time is active.'''

        # get a shared lock for the function
        with locked():
            lock_name = object_name(function)
            if lock_name in synchronized_locks:
                synch_lock = synchronized_locks[lock_name]
            else:
                synch_lock = threading.Lock()
                synchronized_locks[lock_name] = synch_lock

        with locked():
            result = function(*args, **kwargs)

        return result

    return synchronizer

def get_deadline(timeout=None):
    '''
        Return a datetime deadline from timeout.

        'timeout' can be seconds or a timedelta. Default is timedelta.max.

        >>> from datetime import datetime
        >>> deadline = get_deadline()
        >>> deadline is None
        True

        >>> deadline = get_deadline(timedelta(seconds=1))
        >>> type(deadline) is datetime
        True

        >>> deadline = get_deadline(1)
        >>> type(deadline) is datetime
        True

        >>> deadline = get_deadline(1.1)
        >>> type(deadline) is datetime
        True

        >>> deadline('bad timeout value')
        Traceback (most recent call last):
        ...
        TypeError: 'datetime.datetime' object is not callable
    '''

    if timeout is None:
        deadline = None
    elif isinstance(timeout, timedelta):
        deadline = now() + timeout
    elif isinstance(timeout, (float, int)):
        deadline = now() + timedelta(seconds=timeout)
    else:
        raise ValueError(f'timeout must be one of (seconds, timedelta, None), not {type(timeout)}')

    # log(f'deadline: {deadline}')
    return deadline

def connect_to_server(sock, server_required=True):
    ''' Connect to Safelock. '''

    connected = False

    try:
        sock.connect(BIND_ADDR)

    except ConnectionRefusedError:
        if server_required:
            msg = f'Requires safelock package available on PyPI. No lock server at {SAFELOCK_HOST}:{SAFELOCK_PORT}'
            log.error(msg)
            raise LockFailed(msg)

        else:
            log.warning(f'No lock server at {SAFELOCK_HOST}:{SAFELOCK_PORT}, but server_required={server_required}')

    else:
        connected = True

    return connected


if __name__ == "__main__":

    import doctest
    doctest.testmod()
