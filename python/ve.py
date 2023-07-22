'''
    Virtualenv without shell scripts.

    Copyright 2011-2023 solidlibs
    Last modified: 2023-05-17

    No more shell script wrappers with "cd VIRTUALENV_DIR ; bin/activate".
    Just pure python scripts using virtualenv.

    Example::

        import ve
        ve.activate()

        import ... # from virtualenv

        ... code to run in virtualenv ...

    Example::

        from ve import venv

        with venv():
            import ... # from virtualenv
            ... code to run in virtualenv ...

        with venv(other_vdir):
            ... code to run in a different virtualenv ...

        ... code to run outside of virtualenv ...

    This module should be installed system wide, not inside a virtualenv.

    If no virtualenv directory is supplied to activate() or venv(),
    this module will search the calling module's dir and its
    parent dirs for a virtualenv. See virtualenv_dir().

    For maintainers: This module should never have any imports
    except from the standard python library. This allows you to import
    this module, activate a virtualenv, and then import other modules
    from that virtualenv.

    Do not import anything non-standard in this module at global scope.
    If you really need a non-standard import, import in a local scope.
    Example::

        _log = None

        def log(message):
            global _log
            if _log == None:
                # delayed non-global import, still takes effect globally
                import solidlibs.python.log
                _log = solidlibs.python.log.Log()
            _log(message)

    This module is not named virtualenv because that module is part of the virtualenv
    program itself.

    To do:
        Check whether we are already in an activated virtualenv.

    ::

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import os
import sys
import traceback
from contextlib import contextmanager
from glob import glob

DEBUGGING = True
LOGGING = True

# site_packages_subdir_glob is relative to the virtualenv dir
site_packages_subdir_glob = 'lib/python*/site-packages'

if LOGGING:
    from solidlibs.python.log import Log
    log = Log()

def debug(msg):
    if DEBUGGING:
        if LOGGING:
            log.debug(msg)
        else:
            print(msg)

@contextmanager
def venv(dirname=None, django_app=None, restore=True):
    ''' Context manager to activate a virtualenv.

        There are many steps to set up and run a full test. This module
        reduces errors by automating them. It also tries to run tests
        in parallel when possible.

        Deletes all user logs. Optionally runs static tests, unit tests,
        doctests, and functional tests. The doctests and functional tests
        are run as special cases of unit tests.

        Args:

            dirname: Directory where venv will start the search for
            a virtualenv. The default dirname is the current dir. The search
            includes dirname and its parent dirs.

            django_app: Django module with settings.py. Do not confuse
            this with a django subapp, also confusingly called a django app.

            restore: If True, run as context manager. If False, just
            activate  the virtualenv.

        Returns:
            Nothing.
            Output to the screen reports where the full results can be seen.

        Example::

            from ve import venv

            with venv():

                # imports delayed until in virtualenv
                import ...

                ... code to run in virtualenv ...


        To activate a virtualenv once for a module, use activate().

        This context manager will:
           * Set the VIRTUAL_ENV environment variable to the virtualenv dir
           * Set the current dir to the virtualenv dir
           * Prepend virtualenv/bin to the os environment PATH
           * Prepend sites-packages to sys.path
           * Optionally set the DJANGO_SETTINGS_MODULE environment variable

        If dir is not included or is None, ve searches for a virtualenv.
        See virtualenv_dir().

       On exiting the context, any changes to these system environment
       variables or python's sys.path are lost.

        Virtualenv's 'bin/activate' doesn't work well with fabric. See
        http://stackoverflow.com/questions/1691076/activate-virtualenv-via-os-system
    '''

    # venv is called from solidlibs/wsgi_django.py every time
    # gunicorn restarts (starts?) a worker # DEBUG
    # from solidlibs.python.utils import stacktrace # DEBUG
    # debug(f'called venv() from:\n{stacktrace()}') # DEBUG

    debug(f've.activate(dirname={dirname}, django_app={django_app}, restore={restore})')

    old_virtualenv = os.environ.get('VIRTUAL_ENV')
    old_settings_module = os.environ.get('DJANGO_SETTINGS_MODULE')
    old_path = os.environ.get('PATH')
    old_python_path = list(sys.path)
    try:
        old_cwd = os.getcwd()
    except:   # 'bare except' because it catches more than "except Exception"
        # import late so environment is configured properly
        from solidlibs.os.user import getdir

        old_cwd = getdir()

    if dirname:
        debug(f'starting dirname: {dirname}')
    else:
        debug(f'set dirname to cwd: {old_cwd}')
        dirname = old_cwd

    venv_dir = virtualenv_dir(dirname)
    debug(f'set up virtual_env: {dirname}')

    os.environ['VIRTUAL_ENV'] = venv_dir
    debug(f'venv_dir: {venv_dir}')

    bin_dir = os.path.join(venv_dir, 'bin')
    path_dirs = os.environ['PATH'].split(':')
    if bin_dir not in path_dirs:
        new_path = ':'.join([bin_dir] + path_dirs)
        os.environ['PATH'] = new_path

    if django_app:
        os.environ['DJANGO_SETTINGS_MODULE'] = f'{django_app}.settings'
        debug(f'django settings: {django_app}')

    os.chdir(venv_dir)

    sys.path = venv_sys_path(venv_dir)
    debug(f'sys.path={sys.path}')

    try:
        yield

    finally:

        # activate() isn't a context manager, so it sets restore=False
        if restore:

            debug('finally restoring environment')
            if old_virtualenv:
                os.environ['VIRTUAL_ENV'] = old_virtualenv
            else:
                del os.environ['VIRTUAL_ENV']

            os.environ['PATH'] = old_path

            if old_settings_module:
                os.environ['DJANGO_SETTINGS_MODULE'] = old_settings_module
            else:
                if 'DJANGO_SETTINGS_MODULE' in os.environ:
                    del os.environ['DJANGO_SETTINGS_MODULE']

            try_to_cd_back(old_cwd)

            sys.path[:] = old_python_path

    debug('finished venv()')

def activate(dirname=None, django_app=None):
    ''' Activate a virtualenv.

        Example::

            # before any imports from a virtualenv
            import ve
            ve.activate(dirname)   # or ve.activate()

            # now we can import from the virtualenv
            import ...

        If dirname is not included or is None, ve searches for a virtualenv.
        See virtualenv_dir().

        If you want to enter and then exit the virtualenv, use the context
        manager venv().
    '''

    debug(f've.activate(dirname={dirname}, django_app={django_app})')
    venv(dirname, django_app=django_app, restore=False).__enter__()
    debug('activated ve')

def in_virtualenv(dirname=None):
    ''' Return True if in virtualenv, else return False.

        If dirname is specified, return if in specified venv. '''

    """ This is the method used internally in virtualenv.
        See https://stackoverflow.com/questions/1871549/determine-if-python-is-running-inside-virtualenv """

    in_venv = False

    if 'VIRTUAL_ENV' in os.environ:

        if not dirname:
            dirname = os.environ['VIRTUAL_ENV']

        if dirname == os.environ['VIRTUAL_ENV']:
            bin_dir = os.path.join(dirname, 'bin')
            path_dirs = os.environ['PATH'].split(':')

            if bin_dir in path_dirs:

                if os.path.isdir(bin_dir):
                    in_venv = True

    return in_venv

def virtualenv_dir(dirname=None):
    ''' Return full path to virtualenv dir. Raises exception if the
        specified dirname is not a virtualenv and no virtualenv is found.

        virtualenv_dir() searches for a virtualenv in:
            * dirname
            * any parent dir of dirname
            * any immediate subdir of the above

        If dirname is None (the default), virtualenv_dir() sets it to the
        first of:
            * The VIRTUAL_ENV environment variable
            * a virtualenv in a calling module's dir, or parent dir

        This lets you run a program which automatically finds and then
        activates its own virtualenv. You don't need a wrapper script to
        first activate the virtualenv and then run your python code.

        A virtualenv dir is a dir containing "bin/python", "bin/activate", and
        "bin/pip".

        Since there is probably no virtualenv associated with a dir in the
        system path, links in the PATH env dirs are followed. So for a
        program in a PATH dir which is a link, its dirname is the dir of
        the target of the link.

        If you have a default virtualenv dir that is not in your module's
        directory tree, you can still have ve automatically find it. Create
        a link to the virtualenv dir in the calling module's dir or one of
        its parent dirs.

        Example::

            # if your default virtualenv dir is mydefault/virtualenv
            # and your python code is in /usr/local/bin
            ln --symbolic mydefault/virtualenv /usr/local/bin

        '''

    if dirname:
        vdir = check_dir_for_virtualenv(dirname)

    elif 'VIRTUAL_ENV' in os.environ:
        base_dirname = os.environ['VIRTUAL_ENV']
        vdir = os.path.abspath(base_dirname)

    else:

        vdir = None

        # find the calling program module
        # we want the last caller which is not this module
        stack = traceback.extract_stack()
        debug('stack:')
        for element in stack:
            message = '\n'.join(repr(element))
            debug(message)
        debug(f'__file__: {__file__}')

        # stack filenames end in .py; __file__ filenames end in .pyc or .pyo
        basename, _, extension = __file__.rpartition('.')
        if extension == 'pyc' or extension == 'pyo':
            this_filename = basename + '.py'
        else:
            this_filename = __file__
        debug(f'basename: {basename}')
        debug(f'extension: {extension}')
        debug(f'this_filename: {this_filename}')

        caller_filenames = []
        found_callers = False
        for filename, line_number, function_name, text in stack:
            if not found_callers:
                if filename == this_filename:
                    found_callers = True
                else:
                    #debug(f'caller filename: {filename}')
                    caller_filenames.append(filename)

        # do we want to start the search at the earliest or most recent caller?
        # i.e. do we want to leave the list as is or reverse it?
        # for now most recenty, and so we reverse the list
        debug('reverse caller filenames')
        caller_filenames = reversed(caller_filenames)
        for caller_filename in caller_filenames:
            #debug(f'(reversed) caller filename: {caller_filename}')
            if not vdir:
                """ what's this about?
                # in PATH, follow links
                # we probably don't want to always follow links
                path = os.environ['PATH'].split(':')
                dirname = os.path.dirname(caller_filename)
                debug(f'os.path.islink({caller_filename}): {os.path.islink(caller_filename)}')
                while os.path.islink(caller_filename) and dirname in path:
                    caller_filename = os.readlink(caller_filename)
                """

                dirname = os.path.dirname(caller_filename)
                debug(f'dirname: {dirname}')
                vdir = check_dir_for_virtualenv(dirname)

    if not vdir:
        raise Exception(f'No virtualenv found for {dirname}')

    return vdir

def check_dir_for_virtualenv(dirname):
    ''' Check dir and its parent dirs for a virtualenv. '''

    dirname = os.path.abspath(dirname)

    vdir = None
    done = False
    while not done:

        #debug(f'check_dir_for_virtualenv() dirname: {dirname}')
        if not dirname:
            debug('done because no dirname')
            done = True

        elif dirname == '/':
            debug('done dirname is /')
            done = True

        elif is_virtualenv(dirname):
            debug(f'done because virtualenv found: {dirname}')
            vdir = dirname
            done = True

        else:
            #debug(f'check_dir_for_virtualenv() checking subdirs of : {dirname}')
            for d in os.listdir(dirname):
                if not done:
                    path = os.path.join(dirname, d)
                    if os.path.isdir(path):
                        if is_virtualenv(path):
                            vdir = path
                            done = True
            if done: debug(f'vdir: {vdir}')

        if not done:
            # try the parent dir
            dirname = os.path.dirname(dirname)

    if vdir:
        debug(f'vdir found: {vdir}')

    return vdir

def make(venv_dir):
    ''' Make a python virtual environment.

        Args:
            venv_dir: dir of new virtualenv

        Returns:
            sh() for the venv
    '''

    # verify ensurepip
    try:
        python3('-c', 'import ensurepip', _fg=True)
    except:             # pylint:bare-except -- catches more than "except Exception"
        print('missing ensurepip')
        print('In debian, ensurepip is installed')
        print('by the package python3-venv or python3-full')
        print('Try e.g.:')
        print('    find / | grep ensurepip')
        print('and make sure the dir is in sys.path')
        raise

    os.mkdir(venv_dir)
    python3('-m', 'venv', venv_dir)

def make_v_sh(venv_dir):
    ''' Make sh work with a python virtual environment.

        Args:
            venv_dir: dir of new virtualenv

        Returns:
            sh() for the venv
    '''

    # this can be improved by emulating bin/activate

    # this may be unneeded since we explicitly activate the env below
    activate(venv_dir)

    # activate the venv for subprocesses
    v_environ = os.environ.copy()
    v_environ['PATH'] = f'{venv_dir};{os.environ["PATH"]}'
    v_environ['PYTHONPATH'] = os.path.join(venv_dir, 'lib/python/site-packages')
    # sh customized for the virtualenv
    v_sh = sh(_env=v_environ)

    return v_sh

def is_virtualenv(vdir):
    ''' Return whether specified dir is a virtualenv. '''

    return (
        vdir and
        os.path.exists(os.path.join(vdir, 'bin', 'python')) and
        os.path.exists(os.path.join(vdir, 'bin', 'activate')) and
        os.path.exists(os.path.join(vdir, 'bin', 'pip'))
        )

def venv_sys_path(dirname=None):
    ''' Return sys.path for venv dir '''

    venv_dir = virtualenv_dir(dirname)

    # import late so environment is configured
    from solidlibs.os.command import run

    old_dir = os.getcwd()
    os.chdir(venv_dir)

    # get the sys.path from the virtual env's python
    # ?? should we just use the venv's default bin/python?
    major, _, _, _, _ = sys.version_info
    python_path = os.path.join(venv_dir, f'bin/python{major}')
    result = run(python_path, '-c', 'import sys ; print(sys.path)')
    sys_path_string = result.stdout
    result = eval(sys_path_string)

    try_to_cd_back(old_dir)

    return result

def site_packages_dir(dirname=None):
    ''' Return site-packages dir for venv dir '''

    venv_dir = virtualenv_dir(dirname)

    old_dir = os.getcwd()
    os.chdir(venv_dir)

    local_site_packages_dir = glob(site_packages_subdir_glob)[0]
    result = os.path.abspath(os.path.join(venv_dir, local_site_packages_dir))

    try_to_cd_back(old_dir)

    return result

def package_dir(package, dirname=None):
    ''' Return package dir in venv dir '''

    return os.path.join(site_packages_dir(dirname), package)

def try_to_cd_back(old_cwd):
    # because we may have su'd to another user since we originally
    # cd'd to the old dir, we may not have permission to cd back
    try:
        os.chdir(old_cwd)
    except OSError:
        # just log it
        #log('could not chdir(%s); probably not an error' % old_cwd)
        pass


if __name__ == "__main__":

    import doctest
    doctest.testmod()
