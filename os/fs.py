#!/usr/bin/env python3
'''
    File system.

    Copyright 2008-2023 solidlibs
    Last modified: 2023-05-17
    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import os
import os.path
import shutil
import stat
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime
from stat import S_ISDIR
from subprocess import CalledProcessError

from solidlibs.os.command import run
from solidlibs.os.user import sudo, whoami
from solidlibs.python.log import Log
from solidlibs.python.utils import is_string

log = Log()

empty_dir = None

DEFAULT_PERMISSIONS_DIR_OCTAL = 0o755
DEFAULT_PERMISSIONS_FILE_OCTAL = 0o640

# use strings with chmod command, run('chmod'), and solidlibs.os.fs.chmod()
DEFAULT_PERMISSIONS_DIR = 'u=rwX,g=rX,o=rX'
DEFAULT_PERMISSIONS_FILE = 'u=rw,g=r,o='
''' This produces an unreadable int and ignores the difference in
    chmod between 'x' and 'X'.
try:
    DEFAULT_PERMISSIONS_DIR = (
        stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
        stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP |
        stat.S_IROTH | stat.S_IXOTH)
    assert DEFAULT_PERMISSIONS_DIR == DEFAULT_PERMISSIONS_DIR_OCTAL
    DEFAULT_PERMISSIONS_FILE = (
        stat.S_IRUSR | stat.S_IWUSR |
        stat.S_IRGRP | stat.S_IWGRP |
        stat.S_IROTH | stat.S_IWOTH)
    assert DEFAULT_PERMISSIONS_FILE == DEFAULT_PERMISSIONS_FILE_OCTAL
except:   # pylint:bare-except -- catches more than "except Exception"
    DEFAULT_PERMISSIONS_DIR = DEFAULT_PERMISSIONS_DIR_OCTAL
    DEFAULT_PERMISSIONS_FILE = DEFAULT_PERMISSIONS_FILE_OCTAL
'''

class FileSystemException(Exception):
    pass

@contextmanager
def cd(dirname):
    ''' Context manager to change dir temporarily.

        >>> startdir = '/tmp'
        >>> os.chdir(startdir)
        >>> assert os.getcwd() == startdir
        >>> tempdir = tempfile.mkdtemp()
        >>> with cd(tempdir):
        ...     assert os.getcwd() == tempdir
        ...     assert os.getcwd() != startdir
        >>> assert os.getcwd() == startdir

    '''

    olddir = os.getcwd()
    os.chdir(dirname)
    try:
        yield
    finally:
        try:
            os.chdir(olddir)
        except Exception as ex:
            """ Example:
                  1. root's cwd is /root
                  2. root invokes sudo to run a program that calls cd()
                  3. The user doesn't have permission to cd back to /root
                Workaround is to cd to a safe dir before sudo command.
            """
            log.error(f'could not cd from {dirname} to {olddir}')
            log.error(ex)
            raise

def chmod(mode, path, recursive=False):
    ''' Change permissions of path.

        mode is a string or octal integer for the chmod command.
        Examples::
            'o+rw,g+rw'
            0660
    '''

    # arg order used to be chmod(path, mode, ...), so check types
    # delete this assert if no assertion errors 2015-01-01
    # after we remove this assert, mode can be a string
    assert is_string(path)

    if isinstance(mode, int):
        # chmod wants an octal int, not decimal
        # so if it's an int we convert to an octal string
        oct_mode = oct(mode)
        if 'o' in oct_mode:
            i = oct_mode.find('o')
            oct_mode = oct_mode[i+1:]

        if len(oct_mode) > 4 and not oct_mode.startswith('0'):
            mode = '0' + oct_mode
        else:
            mode = oct_mode

    try:
        if recursive:
            run(*['chmod', '--recursive', mode, path])
        else:
            run(*['chmod', mode, path])
    except CalledProcessError as cpe:
        log.error(f'unable to chmod: path={path}, mode={mode}')
        log.error(cpe)
        raise

def chown(owner, path, recursive=False):
    ''' Change owner of path.

        'owner' can be the user name, uid as an int, or uid as a string.

        Log and reraise any exception.
    '''

    try:
        if recursive:
            run(*['chown', '--recursive', owner, path])
        else:
            run(*['chown', owner, path])
        #log.debug(f'chown(owner={owner}, path=={path})')
    except CalledProcessError as cpe:
        log.error(f'unable to chown: user={whoami()}, owner={owner}, path={path}')
        log.error(cpe)
        raise

    # verify. after we have higher confidence, move this into doctests
    if type(owner) is str and ':' in owner:
        owner, group = owner.split(':')
    else:
        group = None
    try:
        uid = int(owner)
    except ValueError:
        # import delayed to avoid infinite recursion
        from solidlibs.os.user import getuid

        uid = getuid(owner)
    assert getuid(path) == uid, f'uid set to {uid} but is {getuid(path)}'
    if group is not None:
        try:
            gid = int(group)
        except ValueError:
            # import delayed to avoid infinite recursion
            from solidlibs.os.user import getuid

            gid = getgid(group)
        assert getgid(path) == gid, f'gid set to {gid} but is {getgid(path)}'

def chgrp(group, path, recursive=False):
    ''' Change group of path.

        'group' can be the group name, gid as an int, or gid as a string.

        Log and reraise any exception.
    '''

    try:
        if recursive:
            run(*['chgrp', '--recursive', group, path])
        else:
            run(*['chgrp', group, path])
        #log.debug(f'chgrp(group={group}, path=={path})')
    except CalledProcessError as cpe:
        log.error(f'unable to chgrp: user={whoami()}, group={group}, path={path}')
        log.error(cpe)
        raise

    # verify. after we have higher confidence, move this into doctests
    if type(group) is str and ':' in group:
        owner, group = group.split(':')
    else:
        owner = None
    if owner is not None:
        try:
            uid = int(owner)
        except ValueError:
            # import delayed to avoid infinite recursion
            from solidlibs.os.user import getuid

            uid = getuid(owner)
        assert getuid(path) == uid, f'uid set to {uid} but is {getuid(path)}'
    try:
        gid = int(group)
    except ValueError:
        # import delayed to avoid infinite recursion
        from solidlibs.os.user import getuid

        gid = getgid(group)
    assert getgid(path) == gid, f'gid set to {gid} but is {getgid(path)}'

def getmode(path):
    ''' Return permissions (mode) of a path.

        >>> oct(getmode('/var/local/projects/solidlibs/os/fs.py'))
        '0o644'
    '''

    return stat.S_IMODE(os.lstat(path)[stat.ST_MODE])

def getuid(path):
    ''' Return uid of a path. '''

    return os.stat(path).st_uid

def getgid(path):
    ''' Return gid of a path. '''

    return os.stat(path).st_gid

def set_attributes(path, owner=None, group=None, perms=None, recursive=False):
    ''' Set ownership and permissions. '''

    if owner is not None:
        chown(owner, path, recursive)
    if group is not None:
        chgrp(group, path, recursive)
    if perms is not None:
        chmod(perms, path, recursive)

def makedir(dirname, owner=None, group=None, perms=None):
    ''' Make dir with default ownership and permissions.

        Makes parent dirs if needed. If dir already exists, ownership
        and permissions are not changed.

        Use this instead of os.mldir() and os.makedirs().
        Those methods mask out the current umask value
    '''

    if perms is None:
        perms = DEFAULT_PERMISSIONS_DIR

    lock = threading.Lock()
    lock.acquire(1) # 1 means blocking

    try:
        if not os.path.exists(dirname):

            # makedirs(dirname, mode) uses umask, so we also call chmod() explicitly
            #log.debug(f'makedir(dirname={dirname}, owner={owner}, group={group}, perms={oct(perms)})') #DEBUG
            try:
                os.makedirs(dirname)
            except OSError:
                log.error(why_file_permission_denied(dirname, perms))
                raise
            else:
                set_attributes(dirname, owner, group, perms, recursive=True)

    finally:
        lock.release()

    assert os.path.isdir(dirname), f'could not make dir: {dirname}'

@contextmanager
def temp_mount(*args, **kwargs):
    ''' Context manager to mount/unmount a filesystem.

        Example::
            >>> if whoami == 'root':
            ...     mountpoint = tempfile.mkdtemp()
            ...     with temp_mount('/tmp', mountpoint):
            ...         mounted(mountpoint)
            ... else: print(True)
            True
            >>> if whoami == 'root':
            ...     mounted(mountpoint)
            ... else: print(False)
            False
            >>> if whoami == 'root':
            ...     os.rmdir(mountpoint)

        Mounts/unmounts only if was unmounted.
        Leaves the mount point in the original state, mounted or unmounted,
        unless the context block changes the mount state.
    '''

    ''' Needs more tests, especially for --bind/move/make-xxx with umount(args[-1]) '''

    # the last arg is reliably the mount point
    # even with --bind, --move, etc.
    mountpoint = os.path.abspath(args[-1])
    if mounted(mountpoint):
        yield

    else:
        # import delayed to avoid infinite recursion
        from solidlibs.os.user import sudo

        with sudo():
            # last arg is mount point
            log.debug(f'temp mount {mountpoint}')
            mount(*args, **kwargs)

        try:
            yield

        finally:
            # import delayed to avoid infinite recursion
            from solidlibs.os.user import sudo

            with sudo():
                log.debug(f'ummount temp mount {mountpoint}')
                unmount(mountpoint)

def mounts():
    ''' Return filesystem mounts as list.

        List elements are (device, mountpoint, vfstype, options).
        All elements are strings.

        >>> if whoami == 'root':
        ...     m = mounts()
        ...     for knownmount in ['/', '/sys', '/proc', '/dev']:
        ...         assert any(knownmount == mountpoint for (device, mountpoint, vfstype, options) in m)
    '''

    results = []
    with sudo():
        with open('/etc/mtab') as mtab:
            for line in mtab:
                device, mountpoint, vfstype, options, dump, fsck = tuple(line.split())
                results.append((device, mountpoint, vfstype, options))

    return results

def mounted_devices():
    ''' Return list of mounted devices. '''

    return [device
        for device, mountpoint, vfstype, options in mounts()]

def unmounted_block_devices():
    ''' Return list of unmounted devices that may have filesystems,
        i.e. unmounted block devices. '''

    unmounted = []
    mounted = mounted_devices()
    for device in devices():
        # /dev/sda may appear to not be mounted, but /dev/sda1 is
        dev_mounted = False
        for mounted_device in mounted:
            if mounted_device.startswith(device):
                dev_mounted = True
        if not dev_mounted:
            unmounted.append(device)

    return unmounted

def mountpoints():
    ''' Return list of filesystem mountpoints.

        >>> if whoami() == 'root':
        ...    for knownmount in ['/', '/sys', '/proc', '/dev']:
        ...        assert knownmount in mountpoints()
    '''

    return [mountpoint
        for device, mountpoint, vfstype, options in mounts()]

def mount(*args, **kwargs):
    ''' Convenience function for mount. '''

    try:
        all_args = ['mount']
        for arg in args:
            all_args.append(arg)
        run(*all_args, **kwargs)
    except Exception as exc:
        log.debug(exc)
        raise

def unmount_all(dirname, force=False):
    ''' Unmount all points in the named dir.

        If force=True, unmount even if mounts are in use.
    '''

    log.debug(f'unmount all in {dirname}')
    # make sure we have a trailing slash
    dir_prefix = os.path.join(dirname, '')

    # umount last mounted first, dirname last
    try:
        for device, mountpoint, vfstype, options in reversed(mounts()):
            if mountpoint.startswith(dir_prefix):
                unmount(mountpoint, force=force)
    except FileSystemException:
        # still try umount at the top level dir
        pass

    unmount(dirname)

def unmount(mountpoint, force=False):
    ''' Unmount mountpoint.

        If force=True, unmount even if mounts are in use.'''

    if mounted(mountpoint):
        log.debug(f'unmount {mountpoint}')

        try:
            run(*['umount', mountpoint])

        except Exception as exc:
            log.debug(f'error in first attempt to unmount: {mountpoint}')
            log.debug(exc)

            # if still mounted, try to find out why
            if mounted(mountpoint):

                # import delayed to avoid import recursion
                import solidlibs.python.process

                # find what process has the path open
                msg = f'unmount failed: {mountpoint}'
                programs = solidlibs.python.process.programs_using_file(mountpoint)
                if programs:
                    msg += f', in use by {programs}'
                log.debug(msg)

                # try waiting a couple of seconds
                import time # DEBUG
                time.sleep(2) # DEBUG
                if mounted(mountpoint): # DEBUG
                    log.debug(f'still mounted after delay: {mountpoint}') # DEBUG
                    if force:
                        # 'lazy' unmount
                        # see linux - Umount a busy device - Stack Overflow
                        #     http://stackoverflow.com/questions/7878707/umount-a-busy-device
                        log.warning(f"force=True, so trying 'lazy' unmount: {mountpoint}")
                        run(*['umount', '-l', mountpoint])
                        log.debug('delay after lazy unmount')
                        time.sleep(10)

                        if mounted(mountpoint): # DEBUG
                            log.debug(f'still mounted after forced unmont and delay: {mountpoint}') # DEBUG
                            # see linux - Umount a busy device - Stack Overflow
                            #     http://stackoverflow.com/questions/7878707/umount-a-busy-device
                            log.warning(f"force=True and 'lazy' unmount didn't work, so forcing unmount: {mountpoint}")
                            run(*['umount', '-f', mountpoint])

                else: # DEBUG
                    log.debug(f'NOT mounted after delay: {mountpoint}') # DEBUG

                if mounted(mountpoint):
                    raise FileSystemException(msg)

            else:
                log.debug(f'umount had error but path is not mounted: {mountpoint}')

def mounted(path):
    ''' Return True iff path mounted. '''

    return path.rstrip('/') in mountpoints()

def mounted_on(path):
    ''' Return device mounted on path, or None if none. '''

    mounted_device = None
    for device, mountpoint, vfstype, options in mounts():
        # return first matching device
        if mounted_device is not None:
            if path == mountpoint:
                mounted_device = device

    return mounted_device

def devices():
    ''' Return list of devices that may have filesystems. '''

    # block devices may have filesystems
    raw_output = run(*['lsblk', '--noheadings', '--list', '--paths', '--output=NAME']).stdout.decode()
    devices = raw_output.strip().split('\n')
    return devices

def match_parent_owner(path, mode=None):
    ''' Chown to the parent dir's uid and gid.

        If mode is present, it is passed to chmod(). '''

    try:
        statinfo = os.stat(os.path.dirname(path))
        os.chown(path, statinfo.st_uid, statinfo.st_gid)
    except:   # pylint:bare-except -- catches more than "except Exception"
        # probably don't have the right to change the file at all,
        # or to change the owner to the specified user
        log.error('unable to chown: user={}, uid={}, gid={}, path={}'.
            format(whoami(), statinfo.st_uid, statinfo.st_gid, path))
        pass
    finally:
        if mode is not None:
            chmod(mode, path)

def get_unique_filename(dirname, prefix, suffix):
    '''
        Get a unique filename.

        >>> dirname = '/tmp'
        >>> prefix = 'test'
        >>> suffix = 'txt'
        >>> filename = get_unique_filename(dirname, prefix, suffix)
        >>> len(filename) > 0
        True
        >>> filename = get_unique_filename(dirname, prefix, suffix)
        >>> len(filename) > 0
        True
        >>> filename = get_unique_filename(dirname, prefix, suffix)
        >>> len(filename) > 0
        True
    '''

    now = datetime.now()
    base_filename = '%s-%d-%02d-%02d-%02d-%02d-%02d' % (
     prefix, now.year, now.month, now.day, now.hour, now.minute, now.second)
    filename = f'{base_filename}.{suffix}'

    if os.path.exists(os.path.join(dirname, filename)):
        i = 1
        filename = f'{base_filename}-{i:02d}.{suffix}'
        while os.path.exists(os.path.join(dirname, filename)):
            i += 1
            filename = f'{base_filename}-{i:02d}.{suffix}'

    return os.path.join(dirname, filename)

def copy(source, dest, symlinks=True, ignore=None, owner=None, group=None, perms=None):
    ''' Copy source to dest dir.

        See copy_only().

        copy() tries to generally follow the behavior of the
        cp command.

        copy() creates any missing parent dirs of dest.
        File ownership and permissions are also copied.

        If dest is a dir, source is copied into dest.
        An exception is when dest and source have the same basename.
        This is a very common error when the intent is to replace the dest.
        In this case the contents of source are copied to dest.
        This is different from merge() because copy() always deletes the
        dest dir. If you really want a dest named "basename/basename",
        specify it explicitly.

        Otherwise, like cp, source will overwrite any existing dest file.

        Unlike shutil.copytree() the default is symlinks=True. So symlinks
        are copied as symlinks. If you want the links replaced by the
        content, set symlinks=False.

        Set ownership and permissions from keywords, or if None copy from
        the corresponding source file.

        >>> testdir = '/tmp/testcopy'
        >>> if os.path.exists(testdir):
        ...     result = run(*['rm', '--force', '--recursive', testdir])
        >>> result = run(*['mkdir', testdir])

        >>> dir1 = os.path.join(testdir, 'dir1')
        >>> result = run(*['mkdir', dir1])
        >>> assert os.path.exists(dir1)
        >>> dir2 = os.path.join(testdir, 'dir2')
        >>> result = run(*['mkdir', dir2])
        >>> assert os.path.exists(dir2)

        >>> file1 = os.path.join(dir1, 'file1')
        >>> result = run(*['touch', file1])
        >>> file2 = os.path.join(dir1, 'file2')
        >>> result = run(*['touch', file2])

        >>> if whoami() == 'root':
        ...     copy(dir1, dir2)
        ...     dir1_in_2 = os.path.join(dir2, os.path.basename(dir1))
        ...     assert os.path.isdir(dir1_in_2)
        ...     file1_in_dir1_in_2 = os.path.join(dir1_in_2, 'file1')
        ...     assert os.path.exists(file1_in_dir1_in_2)

        ...     dir3 = os.path.join(testdir, 'subdir', 'dir1')
        ...     result = makedir(dir3)
        ...     copy(dir1, dir3)
        ...     dir1_not_in_3 = os.path.join(dir3, os.path.basename(dir1))
        ...     assert not os.path.isdir(dir1_not_in_3)
        ...     file1_in_dir3 = os.path.join(dir3, 'file1')
        ...     assert os.path.exists(file1_in_dir3)
    '''

    # log.debug('copy(source={}, dest={}, symlinks=={}, ignore=={}, owner=={}, group=={}, perms=={})'.
    #    format(source, dest, symlinks, ignore, owner, group, perms))

    # source must exist, but a dangling link is acceptable
    if not os.path.exists(source) and not os.path.islink(source):
        raise ValueError(f'source "{source}" does not exist')

    if symlinks and os.path.islink(source):
        dest = os.path.join(dest, os.path.basename(source))
        if os.path.exists(dest):
            # log.debug(f'copy() source is link but dest exists, remove dest: {dest}')
            os.remove(dest)
        os.symlink(os.readlink(source), dest)

    else:

        if os.path.isdir(dest):
            # append the source's basename to dest if the source
            # and destination basenames are different
            # leave an explicit "basename/basename" dest alone.
            if os.path.basename(dest) != os.path.basename(os.path.dirname(dest)):
                if os.path.basename(source) != os.path.basename(dest):
                    dest = os.path.join(dest, os.path.basename(source))
                    log.debug(f'copy() set path to include source basename: {dest}')

        if os.path.exists(dest):
            log.debug(f'copy() remove dest: {dest}')
            run(*['rm', dest, '--force', '--recursive'])

        if os.path.isdir(source):

            unmount_all(source)

            if (symlinks is True and ignore is None):
                # log.debug(f'copy() cp({source}, {dest}, archive=true)')
                run(*['cp', source, dest, '--archive'])
                set_attributes(dest, owner, group, perms, recursive=True)

            else:
                # log.debug(f'copy(..., symlinks={symlinks}, ignore={ignore})')
                makedir(dest)
                # copystat does *not* affect owner and group
                shutil.copystat(source, dest)
                set_attributes(dest, owner=owner, group=group, recursive=True)

                files = os.listdir(source)
                if ignore is None:
                    ignored = []
                else:
                    ignored = ignore(source, files)
                    # log.debug(f'copy() ignored set to {ignored}')

                for file in files:

                    source_path = os.path.join(source, file)
                    if source_path not in ignored:
                        # log.debug('copy() recursing')
                        copy(source_path, dest,
                             symlinks=symlinks, ignore=ignore, owner=owner, group=group, perms=perms)

        else:
            run(*['cp', source, dest, '--preserve'])
            set_attributes(dest, owner, group, perms, recursive=True)

    log.debug('after copy: dest={}, owner=={}, group=={}, perms=={})'. # DEBUG
        format(dest, getuid(dest), getgid(dest), oct(getmode(dest)))) # DEBUG

def copy_only(source, dest):
    ''' Copy 'source' to 'dest'.

        'dest' must not exist. This greatly reduces accidental overwrites.

        Attempts to preserve metadata.
    '''

    if os.path.exists(dest):
        raise ValueError(f'destination already exists: {dest}')

    if os.path.isfile(source):
        shutil.copy2(source, dest)
    elif os.path.isdir(source):
        shutil.copytree(source, dest)
    else:
        raise ValueError(f'unrecognized file type: {source}')

def merge(source, dest, symlinks=True, force=True, ignore=None, owner=None, group=None, perms=None):
    ''' Merge source to dest dir.

        Like shutil.copytree(), but merges with existing dest dir.
        Unlike shutil.copytree(), symlinks and force default to True.
        This behavior is compatible with solidlibs.os.fs.copy(), and seems to
        almost always be what we want.

        Set ownership and permissions from keywords, or if None copy from
        the corresponding source file.
    '''

    ''' Largely copied from http://code.activestate.com/lists/python-list/191783/
        which in turn is largely copied from shutil.copytree(). '''

    def remove_dest(destname):
        if os.path.lexists(destname) and force:
            log.debug(f'removing {destname}')
            os.remove(destname)
            # assert not os.path.exists(destname) # DEBUG

    if not os.path.exists(source):
        raise ValueError(f'source "{source}" does not exist')

    if not os.path.isdir(dest):
        raise ValueError(f'dest "{dest}" must be a dir')

    # log.debug('merge(source={}, dest={}, symlinks=={}, force=={}, ignore=={}, owner=={}, group=={}, perms=={})'.
    #     format(source, dest, symlinks, force, ignore, owner, group, perms))

    names = os.listdir(source)
    if ignore is not None:
        ignored_names = ignore(source, names)
    else:
        ignored_names = set()

    errors = []

    for name in names:
        if name not in ignored_names:

            sourcename = os.path.join(source, name)
            destname = os.path.join(dest, name)

            try:
                if symlinks and os.path.islink(sourcename):
                    linkto = os.readlink(sourcename)
                    # log.debug(f'merge() symlink({linkto}, {destname})') #DEBUG
                    remove_dest(destname)
                    os.symlink(linkto, destname)

                elif os.path.isdir(sourcename):
                    if not os.path.isdir(destname):
                        mode = getmode(sourcename)
                        # log.debug(f'merge() makedirs({destname}, {mode})') #DEBUG
                        makedir(destname, perms=mode)
                    merge(sourcename, destname,
                        symlinks=symlinks, ignore=ignore, force=force,
                        owner=owner, group=group, perms=perms)

                else:
                    # log.debug(f'merge() copy2({sourcename}, {destname})') #DEBUG
                    remove_dest(destname)
                    shutil.copy2(sourcename, destname)
                    set_attributes(destname, owner=owner, group=group, recursive=True)

                    mode = perms or getmode(sourcename)
                    #log.debug(f'  src mode: {oct(getmode(sourcename))}') #DEBUG
                    chmod(mode, destname)
                # XXX What about devices, sockets etc.?

            except (IOError, os.error) as why:
                log.debug(f'could not merge: {name}')
                errors.append((sourcename, destname, str(why)))

            # catch the shutil.Error from the recursive merge so that we can
            # continue with other files
            except shutil.Error as err:
                log.debug(f'could not merge: {name}')
                errors.extend((sourcename, destname, err.args[0]))

    if errors:
        raise shutil.Error(errors)

def move(source, dest, owner=None, group=None, perms=None):
    ''' Move source to dest.

        move() tries to generally follow the behavior of the
        'mv --force' command.

        move() creates any missing parent dirs of dest.

        If dest is a dir, source is copied into dest.

        Otherwise, source will overwrite any existing dest.

        >>> import os.path, tempfile

        >>> def temp_filename(dir=None):
        ...     if dir is None:
        ...         dir = test_dir
        ...     handle, path = tempfile.mkstemp(dir=dir)
        ...     # we don't need the handle
        ...     os.close(handle)
        ...     return path
        >>>
        >>> test_dir = tempfile.mkdtemp()
        >>>
        >>> # test move to dir
        >>> source = temp_filename()
        >>> dest_dir = tempfile.mkdtemp(dir=test_dir)
        >>> move(source, dest_dir)
        >>> assert not os.path.exists(source)
        >>> basename = os.path.basename(source)
        >>> assert os.path.exists(os.path.join(dest_dir, basename))
        >>>
        >>> # test move to new filename
        >>> source = temp_filename()
        >>> dest_filename = temp_filename(dir=test_dir)
        >>> move(source, dest_filename)
        >>>
        >>> # test move to existing filename
        >>> DATA = 'data'
        >>> source = temp_filename()
        >>> dest_filename = temp_filename()
        >>> with open(source, 'w') as sourcefile:
        ...     sourcefile.write(DATA)
        4
        >>> move(source, dest_filename)
        >>> assert not os.path.exists(source)
        >>> assert os.path.exists(dest_filename)
        >>> with open(dest_filename) as destfile:
        ...     assert DATA == destfile.read()
        >>>
        >>> # clean up
        >>> result = run(*['rm', '--force', '--recursive', test_dir])
        >>> assert result.returncode == 0
    '''

    parent_dir = os.path.dirname(dest)
    if not os.path.exists(parent_dir):
        makedir(parent_dir, owner=owner, group=None, perms=None)
    run(*['mv', '--force', source, dest])
    set_attributes(dest, owner, group, perms, recursive=True)

def clonedirs(sourceroot, destroot, destdir, owner=None, group=None, perms=None):
    ''' Make destdir within destroot. Make any needed intermediate-level
        directories.

        Any mountpoints in sourceroot are unmounted.

        The destdir is relative, and so can not start with '/'.

        Set ownership and permissions from keywords, or if None copy from
        the corresponding dir in sourceroot.

        Only directories are cloned, not data files.

        >>> testroot = '/tmp/test-clonedirs'
        >>> sourceroot = os.path.join(testroot, '1')
        >>> destroot = os.path.join(testroot, '2')
        >>> destdir = 'x/y/z'

        >>> if os.path.exists(sourceroot):
        ...     shutil.rmtree(sourceroot)
        >>> if os.path.exists(destroot):
        ...     shutil.rmtree(destroot)
        >>> assert not os.path.exists(sourceroot)
        >>> assert not os.path.exists(destroot)

        >>> sourcepath = os.path.join(sourceroot, destdir)
        >>> makedir(sourcepath)

        >>> makedir(destroot)

        >>> destpath = os.path.join(destroot, destdir)
        >>> assert not os.path.exists(destpath)
        >>> if whoami == 'root':
        ...     clonedirs(sourceroot, destroot, destdir)
        ...     os.path.isdir(destpath)
        ... else:
        ...     print(True)
        True
    '''

    if not os.path.exists(sourceroot):
        raise ValueError(f'dir does not exist: {sourceroot}')
    if not os.path.exists(destroot):
        raise ValueError(f'dir does not exist: {destroot}')
    if destdir.startswith('/'):
        raise ValueError(
            f'dest dir must be relative. It can not start with /: {destdir}')

    sourcepath = os.path.join(sourceroot, destdir)
    destpath = os.path.join(destroot, destdir)

    log.debug(f'clonedirs sourcepath={sourcepath}, destpath={destpath}')
    if type(perms) is int:
        log.debug(f'   owner={owner}, group={group}, perms={oct(perms)}')
    else:
        log.debug(f'   owner={owner}, group={group}, perms={perms}')

    # a chroot might have active mounts
    unmount_all(sourcepath)

    if os.path.exists(destpath):
        # if it's a dir, we're done
        if os.path.isfile(destpath):
            raise ValueError(f'dest dir is not a dir: {destdir}')

    else:
        # make any needed parent dirs
        parent = os.path.dirname(destdir)
        clonedirs(sourceroot, destroot, parent, owner, group, perms)

        if perms is None:
            perms = getmode(sourcepath)
        makedir(destpath, owner, group, perms)

def remove(path):
    ''' Remove the path.

        If path is a dir, empty it first by rsyncing an empty dir to the
        path. With a large directory this is much faster than rm or
        shutil.rmtree().

        It is not an error if the path does not exist.

        If path is a link, only remove the link, not the target.

        If path is a mount, raise ValueError.
    '''

    global empty_dir

    if os.path.exists(path):

        if empty_dir is None:
            empty_dir = tempfile.mkdtemp(prefix='solidlibs.os.fs.empty.')

        if os.path.ismount(path):
            raise ValueError(f'path is mount point: {path}')

        if os.path.islink(path) or os.path.isfile(path):
            run(*['rm', '--force', path])

        else:
            assert os.path.isdir(path)

            run(*['rm', '--force', '--recursive', path])

    assert not os.path.exists(path), f'could not remove {path}'

def relative_path(path):
    ''' Return path as relative path, with no leading or trailing '/'. '''

    return path.strip('/')

def filemode(st_mode):
    ''' Convert integer file permissions to an octal string.

        Function named after python 3.3 os.stat.filemode().

        See python - How to convert a stat output to a unix permissions string - Stack Overflow
            http://stackoverflow.com/questions/17809386/how-to-convert-a-stat-output-to-a-unix-permissions-string

        >>> import os, stat, tempfile

        >>> fd, filename = tempfile.mkstemp()
        >>> os.close(fd)

        >>> # rwx for user and group
        >>> os.chmod(filename, stat.S_IRWXU | stat.S_IRWXG)

        >>> filemode(os.stat(filename).st_mode)
        '-rwxrwx---'

        >>> os.remove(filename)
    '''

    try:
        if S_ISDIR(st_mode):
            is_dir = 'd'
        else:
            is_dir = '-'
    except:   # pylint:bare-except -- catches more than "except Exception"
        is_dir = '-'
    octal_to_readable = {
        '7':'rwx',
        '6' :'rw-',
        '5' : 'r-x',
        '4':'r--',
        '3':'-wx',
        '2':'-w-',
        '1':'--x',
        '0': '---'}
    perm = str(oct(st_mode)[-3:])
    return is_dir + ''.join(octal_to_readable.get(x,x) for x in perm)

@contextmanager
def restore_file(filename):
    ''' Context manager restores a file to its previous state.

        If the file exists on entry, it is backed up and restored.

        If the file does not exist on entry and does exists on exit,
        it is deleted.
    '''

    exists = os.path.exists(filename)

    if exists:
        # we just want the pathname, not the handle
        # tiny chance of race if someone else gets the temp filename
        handle, backup = tempfile.mkstemp()
        os.close(handle)
        run(*['cp', '--archive', filename, backup])

    try:
        yield

    finally:
        if os.path.exists(filename):
            run(*['rm', filename])
        if exists:
            # restore to original state
            run(*['mv', backup, filename])

def edit_file_in_place(filename, replacements, regexp=False, lines=False):
    ''' Replace text in file.

        'replacements' is a dict of {old: new, ...}.
        Every occurence of each old string is replaced with the
        matching new string.

        If regexp=True, the old string is a regular expression.
        If lines=True, each line is matched separately.

        Perserves permissions.

        >>> # note double backslashes because this is a string within a docstring
        >>> text = (
        ...     'browser.search.defaultenginename=Startpage HTTPS\\n' +
        ...     'browser.search.selectedEngine=Startpage HTTPS\\n' +
        ...     'browser.startup.homepage=https://tails.boum.org/news/\\n' +
        ...     'spellchecker.dictionary=en_US')

        >>> f = tempfile.NamedTemporaryFile(mode='w', delete=False)
        >>> f.write(text)
        178
        >>> f.close()

        >>> HOMEPAGE = 'http://127.0.0.1/'
        >>> replacements = {
        ...     'browser.startup.homepage=.*':
        ...         f'browser.startup.homepage={HOMEPAGE}',
        ...     }

        >>> edit_file_in_place(f.name, replacements, regexp=True, lines=True)

        >>> with open(f.name) as textfile:
        ...     newtext = textfile.read()
        >>> assert HOMEPAGE in newtext

        >>> os.remove(f.name)
    '''

    # import delayed to avoid infinite recursion
    from solidlibs.python.utils import replace_strings

    lines_changed = False

    log.debug(f'edit file in place: {filename}, replacements {replacements}')

    # sometimes replace_strings() gets a type error
    for old, new in replacements.items():
        assert is_string(old), f'replacement old "{old}" should be string but is type {type(old)}'
        assert is_string(new), f'replacement new "{new}" should be string but is type {type(new)}'

    # read text
    mode = os.stat(filename).st_mode
    with open(filename) as textfile:
        text = textfile.read()

    if lines:
        newtext = []
        for line in text.split('\n'):
            # sometimes replace_strings() gets a type error
            assert is_string(line), f'line should be string but is {type(line)}'
            newline = replace_strings(line, replacements, regexp)
            if not lines_changed:
                lines_changed = newline != line
            newtext.append(newline)
        text = '\n'.join(newtext)
    else:
        text = replace_strings(text, replacements, regexp)

    if lines_changed:
        # write text
        with open(filename, 'w') as textfile:
            textfile.write(text)
        os.chmod(filename, mode)
        assert mode == os.stat(filename).st_mode
    else:
        log.debug('no lines changed')

def why_file_permission_denied(pathname, mode='r'):
    ''' Return string saying why file access didn't work for the current user.

        Checks parent directories.

        If access mode is allowed, returns None.

        mode::
            r       read
            w       write
            x       execute
            s       search
            a,+     append

        The default mode is 'r'. 's' is treated as 'x'. '+' is treated as 'w'.

        Warning: From Python docs on the os module:

            Note I/O operations may fail even when access() indicates
            that they would succeed, particularly for operations on
            network filesystems which may have permissions semantics
            beyond the usual POSIX permission-bit model.

        Example::
                try:
                    os.makedirs(new_dir)
                except PermissionError as perr:
                    why = why_file_permission_denied(new_dir, mode='ws')
                    log(f"os.makedirs('{new_dir}') failed: {why}")
                    raise
    '''

    if type(mode) == int:
        mode = filemode(mode)

    reason = None
    while pathname and reason is None:

        for perm in mode:

            if (('r' in perm and not is_readable(pathname)) or
                (('w' in perm or 'a' in perm or '+' in perm) and not is_writeable(pathname)) or
                (('x' in perm or 's' in perm) and not is_executable(pathname))):

                reason = f'no "{perm}" access for {pathname}'

        if pathname:
            # remove last component of pathname
            parts = pathname.split('/')
            pathname = '/'.join(parts[:-1])

    if reason:
        reason += f' as user {whoami()}'

    return reason

def replace_file(filename, content):
    ''' Replace or create file content.

        Perserves permissions.
    '''

    if os.path.exists(filename):
        mode = os.stat(filename).st_mode
    else:
        mode = None
    with open(filename, 'w') as f:
        f.write(content)
    if mode is not None:
        os.chmod(filename, mode)
        assert mode == os.stat(filename).st_mode

def is_readable(path, effective_ids=True):
    ''' Return whether the path is readable by the current user '''

    return os.access(path, os.R_OK, effective_ids=effective_ids)

def is_writeable(path, effective_ids=True):
    ''' Return whether the path is writeable by the current user '''

    return os.access(path, os.W_OK, effective_ids=effective_ids)

def is_executable(path, effective_ids=True):
    ''' Return whether the path is executable, or if a dir searchable,
        by the current user '''

    return os.access(path, os.X_OK, effective_ids=effective_ids)

def flush(f):
    ''' Flush all file buffers to disk.

        'f' is a file object. The file object must have a fileno() function.
    '''

    # see python docs for os.fsync(fd)
    f.flush()
    os.fsync(f.fileno())

def get_dir_size(start_path = '.'):
    ''' Return size of dir including subdirs. '''

    # from Calculating a directory's size using Python? - Stack Overflow
    #      https://stackoverflow.com/questions/1392413/calculating-a-directorys-size-using-python

    total_size = 0
    for dirpath, __, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)

    return total_size


if __name__ == "__main__":
    if whoami() == 'root':
        import doctest
        doctest.testmod()
    else:
        print("fs's doctests must be run as root")
