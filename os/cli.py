#!/usr/bin/env python3
'''
    Command line interface.

    A wrapper for the pexpect module.
    The Responder class responds to prompts from programs.

    WARNING: All inputs to the cli module must be sanitised for security.

    Copyright 2013-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.

    This might work instead:
        import os
        import subprocess
        from pexpect import fdpexpect

        program = ['/path/to/command', '--arg1', 'value1', '--arg2', 'value2']
        devNull = open(os.devnull, 'w')
        command = subprocess.Popen(program, stdout=devNull,
                                   stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        child = fdpexpect.fdspawn(command.stderr)
        child.expect('hi')
'''
import os
import re

from solidlibs.python.log import Log

log = Log()

class CliException(Exception):
    pass

class Responder():
    ''' Run a command line interface program with responses.

        'responses' is a list of::
            [(PROMPT, RESPONSE), ...]
        The PROMPT is a python regular expression so be careful
        to escape everything, as needed.

        >>> from solidlibs.os.user import whoami
        >>> if whoami() == 'root':
        ...     responses = [
        ...        ('Are you sure you want to continue connecting (yes/no)? ', 'n'),
        ...        ("Please type 'yes' or 'no':", 'no'),
        ...        ('$', 'exit'),
        ...      ]
        ...     responder = Responder(responses, 'ssh', 'localhost', _clilog=log).run()

        >>> if whoami() == 'root':
        ...     responses = [
        ...       ('localhost:.*?$ ', 'ls'),
        ...       ('localhost:.*?$ ', 'exit'),
        ...      ]
        ...     responder = Responder(responses, 'ssh', 'localhost').run()

        >>> if whoami() == 'root':
        ...     password = 'delete-this-user'
        ...     responses = [
        ...                  ('Enter new UNIX password: ', password),
        ...                  ('Retype new UNIX password: ', password),
        ...                  ('Full Name []: ', None),
        ...                  ('Room Number []: ', None),
        ...                  ('Work Phone []: ', None),
        ...                  ('Home Phone []: ', None),
        ...                  ('Other []: ', None),
        ...                  ('Is the information correct? [Y/n] ', 'y'),
        ...                  ]
        ...     responder = Responder(responses, 'adduser', 'deleteme').run()
        ...     run('deluser', 'deleteme').returncode
        ... else:
        ...     print('0')
        0
    '''

    PRINT_LOG = False

    def __init__(self, responses, program, *args, **kwargs):
        self._clilog = None

        self.responses = responses
        self.command_line = f'{program}'

        for arg in args:
            self.command_line += ' '
            self.command_line += str(arg)
        for key, value in kwargs.items():
            self.command_line += ' '
            self.command_line += f'{key}={value}'
        log.debug(f'Responder command: "{self.command_line}"')

    def run(self):

        # import late in case its not available at the start
        import pexpect   # pylint: disable=import-outside-toplevel

        child = pexpect.spawn(self.command_line, encoding='utf-8', echo=False, logfile=log)

        log('responses:')
        for prompt, response in self.responses:
            log.debug(f'    response to {repr(prompt)} is {response}')
            child.expect(prompt)
            if response:
                child.sendline(response)
            else:
                log.warning('click return')
                child.sendline()

        try:
            child.interact()
        except pexpect.exceptions.TIMEOUT as pet:
            self._log(str(pet))
        except:    # pylint: disable=bare-except  # It catches more than "Exception"
            self._log(str(child))
            raise

        child.close()
        self._log(f'exit status: {child.exitstatus}')
        self._log(f'signal status: {child.signalstatus}')

        return child.exitstatus

    def _log(self, line):
        ''' Log line. '''

        stripped_line = line.strip('\n')
        log.debug(f'output: {stripped_line}')
        if self._clilog:
            self._clilog(line)
        elif self.PRINT_LOG:
            print(f'(no cli_log) {stripped_line}')

def minimal_env(user=None):
    '''
        Get very minimal, safe chroot env.

        Be sure to validate anything that comes from environment variables
        before using it. According to David A. Wheeler, a common cracker's
        technique is to change an environment variable.

        If user is not set, gets the user from solidlibs.os.user.whoami(). This
        can flood /var/log/auth.log, so call with user set when you can.

        >>> from solidlibs.os.user import whoami
        >>> env = minimal_env()
        >>> '/bin:/usr/bin:/usr/local/bin' in env['PATH']
        True
        >>> if whoami() == 'root':
        ...     '/sbin:/usr/sbin:/usr/local/sbin' in env['PATH']
        ... else:
        ...     '/sbin:/usr/sbin:/usr/local/sbin' not in env['PATH']
        True
    '''

    # import delayed to avoid recursive imports
    from solidlibs.os.user import whoami   # pylint: disable=import-outside-toplevel

    if not user:
        user = whoami()

    env = {}

    # use a minimal path
    if user == 'root':
        env['PATH'] = '/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:/usr/local/sbin'
    else:
        env['PATH'] = '/bin:/usr/bin:/usr/local/bin'

    env_var = 'HOME'
    if env_var in os.environ:
        var = os.environ[env_var]
        # make sure the home directory is something reasonable and reasonably safe
        # Wheeler's Secure Programming warns against directories with '..'
        var = os.path.abspath(var)
        if os.path.exists(var):
            env[env_var] = var

    env_var = 'TZ'
    if env_var in os.environ:
        var = os.environ[env_var]
        # only set the variable if it's reasonable
        m = re.match('^([A-Za-z]+[A-Za-z_-]*/?[A-Za-z_-]*/?[A-Za-z_-]*?[A-Za-z0-9]*)$', var)
        if m and (m.group(1) == var):
            env[env_var] = var

    env_var = 'IFS'
    if env_var in os.environ:
        # force the variable to a known good value
        env[env_var] = "$' \t\n'"

    env_var = 'LC_ALL'
    if env_var in os.environ:
        # force the variable to a known good value
        env[env_var] = 'C'

    return env


if __name__ == "__main__":
    import doctest
    doctest.testmod()
