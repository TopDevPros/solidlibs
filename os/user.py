'''
    User utilities.

    Copyright 2010-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

from contextlib import contextmanager
import grp
import os
import pwd
import sys

from solidlibs.os.command import run
from solidlibs.python.log import Log


log = Log()

def whoami():
    ''' Get name of current user.

        Calling whoami() via run() writes to /var/log/auth.log.
        To avoid flooding that log, try to cache the result from
        whoami() when you can.

        >>> assert whoami() == run('whoami').stdout
        >>> assert whoami() == pwd.getpwuid(os.geteuid()).pw_name
    '''

    """
        Two methods, each of which is noisy in a different way.
        Calling getuid_name(os.geteuid()) adds systemd-hostnamed
        entries in syslog.
        Calling run('whoami').stdout adds noise to solidlibs.os.command.log
        and master.log.
    """

    # who = getuid_name(os.geteuid())
    who = run('whoami').stdout
    return who

def require_user(user):
    ''' Require a specific current user. '''

    current_user = whoami()
    if current_user != user:
        # import this late to avoid conflicts
        from solidlibs.python.utils import stacktrace
        msg = f'This program must be run as {user}. Current user is {current_user}.'
        log.debug(msg)
        log.debug(stacktrace())
        sys.exit(msg)

def su(newuser, set_home_dir=True):
    ''' Login as newuser.

        Use sudo() if you want to return to the original user later.
        This will usually only work if you call sudo() as root.

        This function only successfully changes the euid, not the uid.
        Programs which use the uid, such as ssh and gpg, need extra help.
        One solution is to prefix commands with "sudo -u USER".
        See the solidlibs.reinhardt.ssh module.

        This function is unreliable with ssh, os.openpty(), and more.
        A workaround is to use sudo in an enclosing bash script. Or::

            # if not user VM_OWNER then relaunch this program
            if whoami().strip() != VM_OWNER:
                os.execvp( 'sudo' , ['sudo', '-u', VM_OWNER] + sys.argv)

        Raises OsError if user does not exist or current
        user does not has permission to log in as new user. '''

    if whoami() != newuser:
        uid = getuid(newuser)
        os.seteuid(uid)
        # why doesn't this work?
        try:
            # See http://stackoverflow.com/questions/7529252/operation-not-permitted-on-using-os-setuid-python
            # if os.fork():
            #     os._exit(0)

            os.setuid(uid)
        except:   # pylint:bare-except -- catches more than "except Exception"
            # print(traceback.format_exc().strip()) # DEBUG
            # print('ERROR IGNORED. Because os.setuid() does not appear to work even for root') # DEBUG
            pass

    require_user(newuser)
    if set_home_dir:
        os.environ['HOME'] = getdir(newuser)

def sudo(username=None, set_home_dir=True):
    ''' Context manager to temporarily run code as another user.

        This will usually only work if you call sudo() as root.

        Use su() if you do not want to return to the original user later.
        If you are root, this function only sets the euid.
        Some programs use the uid instead of the euid, such as ssh or gpg.

        The current user must have the NOPASSWD option set in /etc/sudoers.
        Otherwise sudo will hang. (This is true for sh. Is NOPASSWD needed
        for this function?)

        WARNING: This function is unreliable with ssh, os.openpty(), and more.
        A workaround is to use sudo in an enclosing bash script. Or::

            # if not user VM_OWNER then relaunch this program
            if whoami().strip() != VM_OWNER:
                os.execvp( 'sudo' , ['sudo', '-u', VM_OWNER] + sys.argv)

        >>> import solidlibs.os.user

        >>> original_user = solidlibs.os.user.whoami()
        >>> if original_user == 'root':
        ...
        ...     for user in solidlibs.os.user.users():
        ...         if user != original_user:
        ...
        ...             with solidlibs.os.user.sudo(user):
        ...                 assert solidlibs.os.user.whoami() == user, f'could not sudo as {user}'
        ...             assert solidlibs.os.user.whoami() == original_user
    '''

    @contextmanager
    def null_contextmanager():
        yield

    @contextmanager
    def active_contextmanager():
        """
        # in python 2.7 os.fork() results in
        #     RuntimeError: not holding the import lock
        # apparently python 3 does not have the bug
        # see  http://bugs.python.org/issue18122
        child = os.fork()
        if child:
            try:
                prev_uid = os.getuid()
                uid = getuid(username)
                os.setuid(uid)
                if set_home_dir:
                    os.environ['HOME'] = getdir(username)
                yield
            finally:
                try:
                    os.setuid(prev_uid)
                except:   # pylint:bare-except -- catches more than "except Exception"
                    pass
                if set_home_dir:
                    os.environ['HOME'] = getdir(prev_user)

        else:
            os.waitpid(child, 0)

        """
        try:
            uid = getuid(username)
            if prev_user == 'root':
                os.seteuid(uid)
            else:
                os.setuid(uid)
            # os.setuid(uid) # DEBUG
            if set_home_dir:
                os.environ['HOME'] = getdir(username)
            yield
        finally:
            prev_uid = getuid(prev_user)
            try:
                os.seteuid(prev_uid)
            except:   # pylint:bare-except -- catches more than "except Exception"
                pass
            else:
                if set_home_dir:
                    os.environ['HOME'] = getdir(prev_user)

    if not username:
        username = 'root'
        # log.debug('sudo() using default user root')

    prev_user = whoami()
    if username == prev_user:
        # no need to sudo, and avoid spurious "is not in the sudoers file" error
        context = null_contextmanager()
    else:
        context = active_contextmanager()

    return context

def force(user):
    ''' If current user is not 'user', relaunch program as 'user'.

        Example::

            if solidlibs.os.user.whoami() == 'root':
                root_setup()
                ...

                # drop privs; relaunch program as USER
                solidlibs.os.user.force(USER)

            # continue as USER
            assert whoami() == USER

    '''

    if whoami() != user:

        # import this late to avoid conflicts
        #from solidlibs.os.fs import is_executable
        #this_program = sys.argv[0]
        # we need something like this, but this doesn't work
        # with sudo(user):
        #     assert is_executable(this_program), f'{this_program} must be executable as {user}'

        for f in [sys.stdout, sys.stderr]:
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # stdout and stderr usually aren't' real files
                pass
        os.execvp( 'sudo' , ['sudo', '-u', user] + sys.argv)

def users():
    '''
        Get active users.

        >>> len(users()) > 0
        True

    '''

    return set(run('users').stdout.split())

def getuid(username):
    ''' Return uid for username. '''

    name_info = pwd.getpwnam(username)
    return name_info.pw_uid

def getuid_name(uid):
    ''' Return user name for uid.

        >>> import pwd

        >>> getuid_name('not an int')
        Traceback (most recent call last):
            ...
        ValueError: uid is not an int: not an int

        >>> for entry in pwd.getpwall():
        ...     assert getuid_name(entry.pw_uid) == entry.pw_name
    '''

    try:
        uid = int(uid)
    except ValueError:
        raise ValueError(f'uid is not an int: {uid}')

    name = None
    for entry in pwd.getpwall():
        if entry.pw_uid == uid:
            name = entry.pw_name

    if name is None:
        raise ValueError(f'Not a valid uid {uid}')

    return name

def getgid(groupname):
    ''' Return gid for groupname. '''

    name_info = grp.getgrnam(groupname)
    return name_info.gr_gid

def getgid_name(gid):
    ''' Return group name for gid.

        >>> import grp

        >>> getgid_name('string')
        Traceback (most recent call last):
            ...
        ValueError: gid is not an int: string

        >>> for entry in grp.getgrall():
        ...     assert getgid_name(entry.gr_gid) == entry.gr_name
    '''

    try:
        gid = int(gid)
    except ValueError:
        raise ValueError(f'gid is not an int: {gid}')

    name = None
    for entry in grp.getgrall():
        if entry.gr_gid == gid:
            name = entry.gr_name

    if name is None:
        raise ValueError(f'Not a valid gid {gid}')

    return name

def getdir(username=None):
    ''' Return home dir for username. '''

    if username is None:
        username = whoami()

    name_info = pwd.getpwnam(username)
    return name_info.pw_dir

def sudo_with_path(user, path, *command):
    ''' Run command as user using PATH=path.

        By default sudo does not preserve a PATH.
        This breaks virtualenv, for example.

        The -E switch in sudo is nearly useless.
    '''

    sudo_command_args = sudo_with_path_args(user, path, *command)
    run(*sudo_command_args)

    """
    run('sudo',
        '-u', user,
        f'PATH={path}',
        *command)
    """

def sudo_with_path_args(user, path, *command):
    ''' Add args to command to run as user using PATH=path.

        By default sudo does not preserve a PATH.
        This breaks virtualenv, for example.

        The -E switch in sudo is nearly useless.
    '''

    return ['sudo', '-u', user, f'PATH={path}'] + list(command)


if __name__ == "__main__":

    import doctest
    doctest.testmod()
