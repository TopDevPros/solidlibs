'''
    Alternate log. Primarily for solidlibs.python.log and modules it uses.

    Copyright 2015-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.

    Logs to the file _log.USER.log in the dir returned by tempfile.gettempdir().

    The modules solidlibs.python.log uses cannot use solidlibs.python.log itself. Use solidlibs.python.log instead
    of this module if you can. This module is much less efficient and
    powerful than solidlibs.python.log. To debug this module use print().

    Functions that are used by both log and _log are here.
'''

import os
import pwd
import time
from tempfile import gettempdir
from traceback import format_exc

def log(message, filename=None, mode=None):
    ''' Log message that solidlibs.python.log can't. '''

    if filename is None:
        try:
            user = whoami()
        # we want to catch any type of exception and Exception won't always do that
        except:   # pylint:bare-except -- catches more than "except Exception"
            user = 'unknown'
        filename = os.path.join(gettempdir(), f'_log.{user}.log')
    if mode is None:
        mode = '0666'

    with open(filename, 'a') as logfile:
        current_timestamp = timestamp()
        try:
            # logwriter dies sometimes and stops regular logging
            # but logit itself logs to this alternate log
            # this print should goto the systemd journal
            #    journalctl --unit logit
            # error is e.g.:
            #    2020-04-17 19:21:33,555 too many values to unpack (expected 3)
            logfile.write(f'{current_timestamp} {format_exc()}\n') # DEBUG
            logfile.write(f'{current_timestamp} {message}\n')
        except UnicodeDecodeError:
            from solidlibs.python.utils import is_string

            try:
                logfile.write(f'unable to write message because it is a type: {type(message)}')
                if not is_string(message):
                    decoded_message = message.decode(errors='replace')
                    logfile.write(f'{current_timestamp} {decoded_message}\n')

            except:  # pylint:bare-except -- catches more than "except Exception"
                print(format_exc())


# redir log.debug() etc.
log.debug = log
log.warning = log
log.error = log

def whoami():
    ''' Get user '''

    # do not use solidlibs.os.user.whoami() so we avoid circular imports
    return pwd.getpwuid(os.geteuid()).pw_name

def timestamp():
    ''' Timestamp as a string. Duplicated in this module to avoid recursive
        imports. '''

    current_time = time.time()
    milliseconds = int((current_time - int(current_time)) * 1000)
    formatted_current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    formatted_milliseconds = '{:03}'.format(milliseconds)
    return f'{formatted_current_time},{formatted_milliseconds}'
