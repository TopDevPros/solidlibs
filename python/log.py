#! /usr/bin/python3
'''
    Python logs for humans.

    Requirements:
      * The safelog package available on PyPI.
      * Running safelog server. The server can be started
        by hand or with the included systemd service file.

    Copyright 2008-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.

    >>> from solidlibs.python.log import Log
    >>> log = Log()
    >>> log('init is simple')

    >>> log('logs are easy')

    >>> # log exception
    >>> try:
    ...     raise Exception('log exception and traceback')
    ... except:   # pylint:bare-except -- catches more than "except Exception"
    ...     log.exception()

    >>> # log exception only
    >>> try:
    ...     raise Exception('log exception only')
    ... except:   # pylint:bare-except -- catches more than "except Exception"
    ...     log.exception_only()

    >>> # catch and log all exceptions
    >>> with log.exceptions():
    ...     print('log any exception in this code block')

    >>> # log stacktrace()
    >>> log.stacktrace()

'''

"""
    Developer notes

    To do:
      * Queue entries in client. Send them to server in separate thread.
      * Check in Log() for log server. If none:
        * Send error message to stderr and raise exception, or
        * Write to log directly

    Because the safelog server runs as root, for safety logs are
    restricted to /var/local/log subdirs.

    Python gets confused about circular imports.
    It's best for this module to delay imports of other modules that use
    this module. An alternative is to use the solidlibs.os.command or
    subprocess module here instead of calling the other module.
    Another alternative is delayed import of solidlibs.python.log in the
    other module. Example::

        _log = None
        def log(msg):
            global _log
            if not _log:
                from solidlibs.python.log import Log
                _log = Log()
            _log(message)
        ...
        log(message)

    You can't easily use this module to debug this module, and some modules
    can't import this one, e.g. django's settings.py. There is a tiny
    alternative log module, solidlibs.python._log, which writes to '/tmp/_log...':
        1. Use solidlibs.python.log._debug(..., force=True)
        2. To debug solidlibs.python.log itself, dynamically set it to send its internal
           debugging to  '/tmp/_log...'. Example:

               import solidlibs.python.log
               solidlibs.python.log._DEBUGGING = True # DEBUG

           Then inside solidlibs.python.log:

               _debug(...)

    WARNING: Setting _DEBUGGING to True will destroy isolation of logs for
    different users. This will cause strange seemingly unrelated
    errors and can cost you days of debugging. Leave _DEBUGGING set to
    False except when you're explicitly debugging this module.

    Of course you can use python's built-in logger directly, if the
    current release of logger is reliable. Example::

            import logging
            # since settings.py imports * from this module, settings.py may also use this log
            LOG_FILENAME = 'mydir/settings.log'
            logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG,
                                format='%(asctime)s %(name)s %(levelname)s %(message)s')
            try:
                os.chmod(LOG_FILENAME, 0o666)
            except:   # pylint:bare-except -- catches more than "except Exception"
                pass
            plog = logging.debug

            ...

            plog(...)
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from glob import glob
import os
import re
import shutil
import smtplib
import socket
import sys
from tempfile import NamedTemporaryFile, gettempdir
from traceback import format_exc, format_exception, format_exception_only, format_stack

from solidlibs.os.command import run
import solidlibs.python._log

# constants shared with solidlibs.python.log and logwriter are
# in solidlibs.python.log so they can be imported easily by tools
SAFELOG_HOST = "localhost"
SAFELOG_PORT = 8534
# try to avoid overhead of pickling/json
FIELD_SEPARATOR = '\x01'

# analogous to /var/log
BASE_LOG_DIR = '/var/local/log'

LOGS = {}
_MASTER_LOGS = {}
_USE_MASTER_LOG = True
_NOTIFY_WEBMASTER_ONCE = False

# internal debugging for solidlibs.python.log
_DEBUGGING = False
_DEBUGGING_LOG_REMOVE_DISABLE = False

WORLD_READWRITE_ACCESS = 0o666

# set these values if you want mail sent if a serious error occurs
alert_from_address = None
alert_to_address = None


def _debug(message, force=False, filename=None, mode=None):
    if force or _DEBUGGING:
        solidlibs.python._log.log(f'python.log: {message}', filename=filename, mode=mode)

class _Log():
    ''' Log file.

        >>> from solidlibs.python.log import Log

        >>> log = Log()
        >>> log('log message')

        Since the safelog server runs as root, don't allow logs
        in other dirs.

        >>> import os.path
        >>> path = '/tmp/testlog.log'
        >>> log2 = Log(path)
        >>> log2('log message 2')
        >>> assert not os.path.exists(path)

        >>> import random
        >>> path = '/tmp/non-extent-dir-{random.randint()}/testlog.log'
        >>> log3 = Log(path)
        >>> log('log message 3')
        >>> assert not os.path.exists(path)
    '''

    MAX_STACK = 1000

    log_dir = None
    filename = None

    def __init__(self,
                 filename=None, dirname=None, group=None,
                 recreate=False, verbose=False, audible=False):
        ''' 'filename' is an explicit filename.
            'dirname' is the dir to use with the default log file basename.
            'group' is the group that wns the lof file. Defaults to the group
            for the current user.
            'recreate' will delete any existing log before use.
            'verbose' prints log entries to stdout. The 'verbose' keyword can
            be overridden for a log entry.
            If audible=True, the command line 'say' program will be called
            with the message.
        '''

        self.filename = filename
        self.dirname = dirname
        self.group = group
        self.user = solidlibs.python._log.whoami()
        self.recreate = recreate
        self.verbose = verbose
        self.audible = audible

        self.pathname = get_log_path(filename=self.filename, dirname=self.dirname)
        self.debugging = False
        self.stdout_stack = []

    def __call__(self, message, verbose=None, audible=None, exception=None):
        ''' Output message to log.debug, optionally also to stdout and audibly.

            If verbose=True, this log message will also be printed to stdout.
            If verbose=False, this message will not printed to stdout, even if
            the log was initialized with verbose=True. Default is None, which
            uses the verbose value passed to Log() or Log(, if any).

            If audible=True, the command line 'say' program will be called
            with the message. Otherwise audible is similar to verbose. Since
            voice generation can be nearly unintelligible, the message should
            be very short and used infrequently.

            If exception=True, the last exception will be logged.
        '''

        self.debug(message)
        # previously was "self.write(message)". did some caller specify 'DEBUG', 'INFO' etc?

        if not self.is_master():

            if verbose is None:
                verbose = self.verbose
            if verbose:
                print(f'{solidlibs.python._log.timestamp()} {message}')

            if audible is None:
                audible = self.audible
            if audible:
                try:
                    from solidlibs.python.utils import say
                    say(message)
                except:   # pylint:bare-except -- catches more than "except Exception"
                    pass

            # this is 'exception' passed to __call__()
            if exception:
                self.exception()

    def write(self, message):
        ''' Write message to log.

            write() writes to a log as you would to a file.
            This lets you redirect sys.stdout to the log and log print output
            generated by third party libraries, even if the library uses
            print statements without '>>' or print functions without 'stream='.
        '''

        def notify_webmaster(message):
            ''' Send the message to the webmaster.

                We can't use solidlibs.reinhardt.dmail.send because it imports this module.
            '''

            if alert_from_address is not None and alert_to_address is not None:
                addresses = f'From: {alert_from_address}\nTo: {alert_to_address}'
                msg = f'{addresses}\nSubject: {subject}\n\n{message}\n'
                server = smtplib.SMTP('localhost')
                server.sendmail(alert_from_address, alert_to_address, msg)

        # we don't use @synchronized here because of import errors

        global _NOTIFY_WEBMASTER_ONCE

        try:
            from solidlibs.python.utils import is_string

            if is_string(message):
                self._write(message)
            elif isinstance(message, (bytes, bytearray)):
                # send bytes to self._write()
                self._write(message.decode(errors='replace'))
            else:
                self.write(f'unable to write message because it is a {type(message)}')

            if self.verbose:
                print(message)
            if _USE_MASTER_LOG and not self.is_master():
                if self.user not in _MASTER_LOGS:
                    _MASTER_LOGS[self.user] = Log('master.log', dirname=self.dirname)

                try:
                    logline = f'{os.path.basename(self.pathname)} {message}'
                    _MASTER_LOGS[self.user]._write(logline)
                except UnicodeDecodeError:
                    _MASTER_LOGS[self.user]._write(f'{self.filename} - !! Unable to log message -- UnicodeDecodeError !!')

        except UnicodeDecodeError:
            try:
                _debug(message.decode(errors='replace'))
            except UnicodeDecodeError:
                self.write(f'unable to write message because it is a type: {type(message)}')
                subject = '!! Unable to log message !!'
                self._write(subject)
                if _NOTIFY_WEBMASTER_ONCE:
                    _NOTIFY_WEBMASTER_ONCE = False
                    notify_webmaster(message)

        except Exception:
            if _DEBUGGING:
                sys.exit('debug exit after exception') # DEBUG
            """
            self._write(format_exc())
            subject = '!! Unable to log message !!'
            self._write(subject)
            if _NOTIFY_WEBMASTER_ONCE:
                _NOTIFY_WEBMASTER_ONCE = False
                notify_webmaster(message)
            """
            raise

        #if _DEBUGGING: sys.exit('debug exit without exception') # DEBUG

    def _write(self, message):
        ''' Send message to log file. '''

        try:
            # _debug('_write() self._write') # DEBUG
            log_entry = f'{self.timestamp()} {message}\n'
            # for some reason nulls are getting into the logs
            log_entry.replace('\0', '')
            # we use FIELD_SEPARATOR as a separator later,
            # so we don't want them in the data
            log_entry.replace(FIELD_SEPARATOR, '<<FS>>')
            self._write_log_entry(log_entry)

        except:   # pylint:bare-except -- catches more than "except Exception"
            _debug('_write() after self._write: self.exception') # DEBUG
            self.exception()

    def _write_log_entry(self, log_entry):
        ''' Send line to logserver. '''

        def check_log_entry():
            ok = True
            if FIELD_SEPARATOR in self.user:
                self.warning('solidlibs.python.log: FS in self.user')
                ok = False
            if FIELD_SEPARATOR in basename:
                self.warning('solidlibs.python.log: FS in basename')
                ok = False
            if FIELD_SEPARATOR in log_entry:
                ok = False
                self.warning('solidlibs.python.log: FS in log_entry; binary log messsage?')

            return ok

        def log_line():
            return f'{self.user} {basename} {log_entry.rstrip()}'

        self._check_user()
        basename = os.path.basename(self.pathname)

        # Create a socket (SOCK_STREAM means a TCP socket)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Connect to logserver and send data
            try:
                sock.connect((SAFELOG_HOST, SAFELOG_PORT))

            except ConnectionRefusedError:
                try:
                    msg = f'No log server at {SAFELOG_HOST}:{SAFELOG_PORT}'
                    solidlibs.python._log.log(msg)
                    solidlibs.python._log.log(log_line())
                    sys.exit(msg)

                except:   # pylint:bare-except -- catches more than "except Exception"
                    # probably system is going down and
                    # the log server is already down
                    pass

            else:
                if check_log_entry():
                    _debug(f'send log entry: {log_line()}')
                    data = FIELD_SEPARATOR.join([self.user, basename, log_entry])
                    data = data.encode()
                    sock.sendall(data)

    def info(self, msg, *args, **kwargs):
        ''' Compatibility with standard python logging. '''

        self.log('INFO', msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        ''' Compatibility with standard python logging.

            If the message is an Exception, Log.debug() logs everything we
            know about the Exception. If you are in an exception handler
            block and call Log.warning() etc. and want Exception
            details, also call log.debug(exc).
        '''

        if isinstance(msg, UnicodeError):

            # don't log the bad data; it screws up some editors
            self.debug(format_exception_only(type(msg), msg))
            self.debug('UnicodeError:')
            self.stacktrace()

        elif isinstance(msg, Exception):
            ''' The structure of Exception has changed over time. '''

            exc_type, exc_value, stacktrace = sys.exc_info()

            # is the exc_info for this Exception?
            if (isinstance(exc_value, type(msg)) and
                str(exc_value) == str(msg)):
                self.exception() # was: self.stacktrace()

            else:
                # the msg Exception is not the most recent, so no traceback for this exception
                self.debug('log.debug() called with an exception but no traceback available')
                msg = format_exception_only(type(msg), msg)
                self.log('DEBUG', msg)

            """ is this needed today?
            if msg.args:
                # log any Exception args
                try:
                    msg.args

                except AttributeError:
                    pass

                else:
                    if isinstance(msg.args, tuple):
                        try:
                            self.debug(' '.join(map(str, list(msg.args))))
                        except UnicodeDecodeError:
                            self.debug(b' '.join(map(bytes, list(msg.args))))
                    else:
                        self.debug(msg.args)
            """

        else:
            self.log('DEBUG', msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        ''' Compatibility with standard python logging. '''

        self.log('WARNING', msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        ''' Compatibility with standard python logging. '''

        self.log('ERROR', msg, *args, **kwargs)

    def exception(self):
        ''' Log the current exception.

            Any calls to last_exception() should call exception() instead.
        '''

        exc_type, exc_value, exc_traceback = sys.exc_info()
        # if we are in an 'except' clause
        if exc_type:
            try:
                # sometimes traceback.format_exception() returns a
                # ridiculously short traceback
                lines = format_exception(exc_type, exc_value, exc_traceback)
                msg = ''.join(lines)
                self.debug(msg)
            except:   # pylint:bare-except -- catches more than "except Exception"
                print(f'exc_type: {exc_type}, exc_value: {exc_value}, exc_traceback: {exc_traceback}')

    def exception_only(self):
        ''' Log the current exception type and value, without traceback. '''

        exc_type, exc_value, __ = sys.exc_info()
        # if we are in an 'except' clause
        if exc_type:
            try:
                msg = ''
                for line in format_exception_only(exc_type, exc_value):
                    msg = msg + line.strip()
                self.debug(msg)
            except:  # pylint:bare-except -- catches more than "except Exception"
                print(f'exc_type: {exc_type}, exc_value: {exc_value}')

    def log(self, level, msg, *args, **kwargs):
        ''' Compatibility with standard python logging.

            Utility function to support log.debug(), etc.
            Called as self.log('DEBUG', ...), self.log('INFO', ...), etc.
        '''

        if kwargs:
            args = args + (kwargs,)
        if args:
            message = msg.format(*args)
        else:
            message = msg

        try:
            try:
                level.encode('utf-8')
            except UnicodeDecodeError:
                level = ''

            try:
                if isinstance(message, Exception):
                    message = str(message)
                elif isinstance(message, (bytes, bytearray)):
                    message = message.decode(errors='replace')
            except TypeError:
                # don't change message. but would it be better to still encode as utf8?
                pass
            except UnicodeDecodeError:
                message = '-- message contains unprintable characters --'

            self.write(f'{level} {message}')

        except Exception:
            self.exception()

    def stacktrace(self, msg=None):
        ''' Log full current stacktrace.

            Contrary to the python docs, python often limits the number of
            frames in a stacktrace. This is a full stacktrace.

            >>> import os, os.path
            >>> import time

            >>> TESTLOG = 'test.stacktrace.log'

            >>> log = solidlibs.python.log.Log(TESTLOG)

            >>> def test_func():
            ...     log('test stacktrace()')
            ...     log.stacktrace()

            >>> path = get_log_path(TESTLOG)
            >>> if os.path.exists(path):
            ...     os.remove(path)

            >>> test_func()
            >>> # allow time for the logserver to write the stacktrace
            >>> time.sleep(1)
            >>> with open(path) as infile:
            ...     text = infile.read()
            ...     assert 'test_func' in text, text

            Alternate for exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                lines = format_exception(exc_type, exc_value, exc_traceback,
                                         limit=self.MAX_STACK,
                                         chain=True)
                msg = ''.join(lines).strip()
        '''

        prefix = 'Call stack:\n'
        if msg:
            prefix = f'{msg}: {prefix}:'
        lines = [prefix] + format_stack()[:-1]
        stack = '\t'.join(lines)
        self.debug(stack)

    @contextmanager
    def exceptions(self):
        ''' Context manager to log any exceptions.

            This context manager should also wrap constants, because
            exceptions can occur in constants.
        '''

        try:
            yield

        except Exception:
            self.exception()
            raise

    def is_master(self):
        ''' Return whether this log is a master log. '''

        if not self.pathname:
            self.pathname = get_log_path(filename=self.filename, dirname=self.dirname)
        return os.path.basename(self.pathname) == 'master.log'

    def _check_user(self):
        ''' Detect user changed.

            If no dir was specified, use default dir for user.
        '''

        if not self.dirname:
            if not self.filename.startswith('/'):

                current_user = solidlibs.python._log.whoami()

                if self.user is None:
                    self.user = current_user

                elif self.user != current_user:
                    msg = f'Log user changed from {self.user} to {current_user}.'
                    _debug(msg, force=True)
                    self.user = current_user
                    self.pathname = get_log_path(filename=self.filename, dirname=self.dirname)

    def timestamp(self):
        '''
            >>> l = _Log()
            >>> isinstance(l.timestamp(), datetime)
            True
        '''
        try:
            dt = datetime.utcnow().replace(tzinfo=timezone.utc)
        except:  # pylint:bare-except -- catches more than "except Exception"
            dt = datetime.utcnow()
        return dt

    def flush(self):
        ''' This function is here to make _Log
            compatible with other logging system. '''

        # do not delete the pass as it's needed when we strip all comments
        pass

def Log(filename=None, dirname=None, group=None, recreate=False, verbose=False):
    ''' Return open log. Default is a log for the calling module.

        The default log path is "BASE_LOG_DIR/USER/MODULE.log".
        If filename is specified and starts with a '/', it is the log path.
        If filename is specified and does not start with a '/', it replaces "MODULE.log".
        If dirname is specified, it replaces "BASE_LOG_DIR/USER".

        Log instances are cached by pathname.

        If recreate=True and the log file is not already open, any existing
        log file is removed.

        The function "Log" is capitalized because the behavior of Log()
        is similar to a class. It returns an instance. The reasons
        that a class didn't work are lost to antiquity.

        >>> import os.path
        >>> from solidlibs.python.log import Log

        >>> logname = 'testlog1.log'
        >>> log = Log(logname)
        >>> log('log message')
        >>> log_path = os.path.join(BASE_LOG_DIR,
        ...                solidlibs.python._log.whoami(),
        ...                logname)
        >>> assert log.pathname == log_path, f'{log.pathname} != {log_path}'

        >>> log = Log('testlog2.log', dirname='/tmp/logs')
        >>> log('log message')
        >>> print(log.dirname)
        /tmp/logs

        >>> log = Log('/tmp/testlog3.log')
        >>> log('log message')
        >>> print(log.dirname)
        /tmp
    '''

    logpath = get_log_path(filename=filename, dirname=dirname)

    if logpath in LOGS.keys():
        log = LOGS[logpath]

    else:
        dirname = os.path.dirname(logpath)
        log = _Log(
            filename=filename, dirname=dirname,
            group=group, recreate=recreate, verbose=verbose)
        LOGS[logpath] = log

    return log

def get_log_path(filename=None, dirname=None):
    ''' Returns log path.

        The default log path is "BASE_LOG_DIR/USER/MODULE.log".
        If filename is specified and starts with a '/', it is the log path.
        If filename is specified and does not start with a '/', it replaces "MODULE.log".

        >>> import os.path
        >>> from solidlibs.python.log import Log

        >>> path = get_log_path('testlog1.log', dirname='/tmp/logs')
        >>> assert os.path.basename(path) == 'testlog1.log'
        >>> assert os.path.dirname(path) == '/tmp/logs'

        >>> path = get_log_path('/tmp/testlog2.log')
        >>> assert os.path.basename(path) == 'testlog2.log'
        >>> assert os.path.dirname(path) == '/tmp'

        >>> path = get_log_path('testlog3.log')
        >>> assert os.path.basename(path) == 'testlog3.log'
        >>> assert os.path.dirname(path) == os.path.join(BASE_LOG_DIR, solidlibs.python._log.whoami())

        >>> path = get_log_path()
        >>> 'get_log_path' in path
        True
    '''

    if filename is None:
        from solidlibs.python.internals import caller_module_name
        filename = caller_module_name(ignore=[__file__])
        if filename == '<stdin>':
            filename = '__stdin__'
        else:
            if filename.startswith('..'):
                filename = filename[2:]
            match = re.match('<doctest (.*?)\[', filename)
            if match:
                filename = match.group(1).replace('__main__.', '').lower()

    # sometimes we pass the filename of the caller so strip the end
    if filename.endswith('.py') or filename.endswith('.pyc'):
        filename, _, _ = filename.rpartition('.')

    filename = default_log_filename(filename)
    if dirname is None:
        dirname = default_log_dir()
    else:
        # no relative dir names
        assert dirname.startswith('/')

    logpath = os.path.join(dirname, filename)
    _debug(f'in solidlibs.python.log.get_log_path() logpath: {logpath}') # DEBUG

    return logpath

def default_log_dir():
    '''
       We want to keep the logs together as much as possible,

       The default is /var/local/log/USER. This avoids log ownership conflicts.
    '''

    user = solidlibs.python._log.whoami()
    dirname = os.path.join(BASE_LOG_DIR, user)
    return dirname

def delete_all_logs(dirname=None):
    ''' Delete all files in dir. '''

    if not dirname:
        dirname = default_log_dir()

    if _DEBUGGING_LOG_REMOVE_DISABLE:
        _debug(f'_DEBUGGING_LOG_REMOVE_DISABLE disabled: delete_all_logs() removing {dirname}') #DEBUG

    else:
        # don't delete dirname itself
        entries = glob(os.path.join(dirname, '*'))
        # make sure this dir has at least one log, i.e. is possibly a logs dir
        assert any(entry.endswith('.log') for entry in entries)
        for entry in entries:
            if os.path.isdir(entry):
                shutil.rmtree(entry)
            else:
                os.remove(entry)

def default_log_filename(name):
    ''' Make sure log filenames look like logs. '''
    if name.endswith('.log'):
        log_name = name
    else:
        log_name = f'{name}.log'
    return log_name

def set_alert_addresses(from_address, to_address):
    '''Set the mail addresses to use if serious error detected while logging.
    '''
    global alert_from_address, alert_to_address

    alert_from_address = from_address
    alert_to_address = to_address

def format_args(*args, separator=None):
    ''' Return args as text joined by separator.

        This is an alternative to the standard log args formatting of (roughly)::
            self.debug(message, *args)
                ...
                self.log(message.format(*args)(

        Separator defaults to ': '.
    '''

    def text(arg):
        ''' Filter arg to str. '''

        if isinstance(arg, Exception):
            # assume current exception
            result = format_exc()
        else:
            result = str(arg)

        return result

    separator = separator or ': '

    # remove empty args
    args = filter(bool, args)
    # convert to text
    args = list(map(text, args))

    line = separator.join(args)
    return line

def clear_user_logs(user):
    ''' Clear all logs created by this module for the user.

        The caller must have the correct file permissions.
    '''

    logdir = os.path.join(BASE_LOG_DIR, user)
    if os.listdir(logdir):
        run('rm', f'{logdir}/*')

    # if solidlibs.python.log.DEBUGGING is True, then solidlibs.python.log creates alt logs
    alt_log = f'/tmp/_log.{user}.log'
    if os.path.exists(alt_log):
        os.remove(alt_log)

    default_log = f'/tmp/python.default.{user}.log'
    if os.path.exists(default_log):
        os.remove(default_log)

def _test():
    """
        >>> import solidlibs.python.log

        >>> # if we don't specify a log filename,
        >>> # then solidlibs.python.log uses the calling module,
        >>> # in this case '<doctest...'
        >>> log = solidlibs.python.log.Log('_test.log')

        >>> log.filename
        '_test.log'

        >>> unique_message = f'test message to {log.filename} at {solidlibs.python._log.timestamp()}'
        >>> log(unique_message)

        # give logwriter time to write
        >>> import time
        >>> time.sleep(1)

        >>> logdir = f'/var/local/log/{solidlibs.python._log.whoami()}'
        >>> for basename in ['_test.log', 'master.log']:
        ...     logpath = os.path.join(logdir, basename)
        ...     with open(logpath) as logfile:
        ...         content = logfile.read()
        ...         assert unique_message in content
    """

    # there must be some body to the function other than comments
    # although prospector complains
    pass


# get_log and get were deprecated in 2.6.2 in favor of Log()
get_log = Log
get = Log

if __name__ == "__main__":
    import doctest
    doctest.testmod()
