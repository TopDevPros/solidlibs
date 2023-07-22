#!/usr/bin/env python3
'''
    Run a command using python subprocess.

    This is an attempt to work around python's changing and incorrectly
    documented subprocess and traceback modules.

    Copyright 2018-2023 solidlibs
    Last modified: 2023-05-19
'''

from glob import glob
import os
import shlex
import subprocess
from traceback import format_exc

# log init delayed to avoid circular imports
log = None

def run(*command_args, **kwargs):
    ''' Run a command line.

        Much simpler than using python subprocess directly::

            >>> result = run('echo', 'word1', 'word2')
            >>> result.stdout
            'word1 word2'

        Error handling is easier::
            >>> try:
            ...     result = run('sleep', 'not a number')
            ... except subprocess.CalledProcessError as error:
            ...     'invalid time interval' in error.stderrout
            True

        Returns subprocess.CompletedProcess, or raises
        subprocess.CalledProcessError. Some commands return python
        built-in exceptions, such as FileNotFoundError.

        By default run() captures stdout and stderr. It decodes
        .stdout and .stderr, and adds a combined .stderrout.
        To direct stdout and stderr to sys.stdout and sys.stderr,
        use run_verbose(). This is different from the keyword
        verbose=.

        If verbose is True, run() logs extra information.

        Each command line arg should be a separate run() arg so
        subprocess.check_output can escape args better.

        Unless output_bytes=True, the .stdout, and .stderr attributes
        of subprocess.CompletedProcess are returned as unicode strings, not
        bytes. For example stdout is returned as stdout.decode().strip().
        The default is output_bytes=False. This is separate from
        universal_newlines processing, and does not affect stdin.

        Args are globbed unless glob=False.

        Except for 'output_bytes' and 'glob', all keyword args are passed
        to subprocess.run().

        On error raises subprocess.CalledProcessError.
        The error has an extra data member called 'stderrout' which is a
        string combining stderr and stdout.

        To see the program's output when there is an error::

            try:
                run(...)

            except subprocess.CalledProcessError as cpe:
                print(cpe)
                print(f'error output: {cpe.stderrout}')

        Because we are using subprocess.PIPEs, to avoid zombie processes we would
        need to use subprocess.Popen() instead of subprocess.run(), and call
        subprocess.Popen.communicate(). For simplicity, we generally don't use
        subprocess.Popen() for foreground tasks. Zombie processes are worrisome,
        but do no real harm.

        See https://stackoverflow.com/questions/2760652/how-to-kill-or-avoid-zombie-processes-with-subprocess-module

        run() does not process special shell characters. It treats
        them as plain strings.

        >>> from tempfile import gettempdir
        >>> tmpdir = gettempdir()
        >>> command_args = ['ls', '-l', f'{tmpdir}/solidlibs*']
        >>> kwargs = {'glob': False, 'shell': True}
        >>> result = run(*command_args, **kwargs)
        >>> result.returncode
        0
        >>> len(result.stdout.split()) > 3
        True

        >>> from tempfile import gettempdir
        >>> tmpdir = gettempdir()
        >>> command_args = ['ls', '-l', f'{tmpdir}/solidlibs*']
        >>> kwargs = {'glob': False, 'shell': True}
        >>> result = run(*command_args, **kwargs)
        >>> result.args
        ['ls', '-l', '/tmp/solidlibs*']
        >>> result.returncode
        0

        >>> command_args = ['echo', '"solidlibs*"']
        >>> result = run(*command_args)
        >>> result.returncode
        0

        # check redir of stdin and stdout
        >>> result = run_verbose('echo test', shell=True)
        >>> result.returncode
        0
        >>> result.stdout
        'test'

        # Not working: this test requires human interaction, so it is usually disabled
        <<< p = subprocess.Popen('cat',
                    ...           shell=True,
                    ...           stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        <<< p.close()
        <<< p.returncode
        0
        <<< p.stdout.read()
        'test'

        # <<< result = run_verbose('bash', '-c', 'read x ; while ["$x" !=""] ; do  echo output: $x ; read x ; done')

        >>> try:
        ...     result = run('non-existent-command-xyzzy-unique-4543')
        ... except FileNotFoundError as error:
        ...     type(error) is FileNotFoundError
        True
    '''

    _init_log()
    result = None

    command_args = list(map(str, command_args))

    try:
        args, kwargs = get_run_args(*command_args, **kwargs)

        if kwargs:
            if 'verbose' in kwargs:
                verbose = kwargs['verbose']
                if verbose:
                    log(f'args: {args}')
                    log(f'kwargs: {kwargs}')
                del kwargs['verbose']
            else:
                verbose = False
        else:
            verbose = False

        if 'output_bytes' in kwargs:
            output_bytes = kwargs['output_bytes']
            del kwargs['output_bytes']
            if verbose:
                log(f'output bytes: {output_bytes}')
        else:
            output_bytes = False

        for output in ['stdout', 'stderr']:
            if output not in kwargs:
                kwargs[output] = subprocess.PIPE

        result = subprocess.run(args,
                                check=True,
                                **kwargs)

    except subprocess.CalledProcessError as cpe:
        log.warning(f'command got subprocess.CalledProcessError: {command_args}')
        log(f'subprocess.CalledProcessError format_exc(): {format_exc(chain=True)}') # DEBUG
        cpe = format_output(cpe)
        result = handle_run_error(command_args, cpe)
        raise

    except Exception as e:
        log.warning(f'command got Exception: {command_args}')
        log(f'Exception format_exc(): {format_exc(chain=True)}') # DEBUG
        log.warning(f'error NOT subprocess.CalledProcessError: {type(e)}')
        log(format_exc())
        raise

    else:
        if verbose:
            log(f'command succeeded: {command_args}')
        # log(f'before format_output(result), result: {result}') # DEBUG
        result = format_output(result)
        # log(f'after format_output(result), result: {result}') # DEBUG

    if verbose:
        log(f'after run(), result: {result}') # DEBUG

    return result

def run_verbose(*args, **kwargs):
    ''' Run program with stdout and stderr directed to
        sys.stdout and sys.stderr.

        WARNING: What actually happens is you see stdout and stderr
        after the program runs. This is not interactive.

        This does not test as expected with doctests. That's because
        doctests can't have stdout redirected. So we disable interactive in
        the following test. Under normal circumstances you don't want to set
        interactive to False. If you do not want the command to run interactive,
        just use the run() function.

        >>> result = run_verbose('echo', 'ok')
        >>> result.args
        ['echo', 'ok']
        >>> result.returncode
        0
        >>> result.stdout
        'ok'
        >>> result.stderr
        ''

        >>> from tempfile import gettempdir
        >>> tmpdir = gettempdir()
        >>> kwargs = {'interactive': False}
        >>> command_args = ['ls', '-l', f'{tmpdir}']
        >>> result = run_verbose(*command_args, **kwargs)
        >>> result.args
        ['ls', '-l', '/tmp']
        >>> result.returncode
        0
    '''

    if kwargs is None:
        kwargs = {}

    if 'interactive' not in kwargs:
        kwargs['interactive'] = True

    result = run(*args, **kwargs)

    return result

def background(*command_args, **kwargs):
    ''' Run a command line in background.

        Args:
            *command_args: command line args
            **kwargs: keyword args passed to subprocess.Popen()

        Returns:
            subprocess.Popen instance

        If your command file is not executable and starts with '#!',
        background() will use 'shell=True'.

        Passes along all keywords to subprocess.Popen().
        That means you can force the subprocess to run in the foreground
        with e.g. timeout= or check=. But command.run() is a better
        choice for this case.

        Returns a subprocess.Popen object, or raises
        subprocess.CalledProcessError.

        If you redirect stdout/stderr, be sure to catch execution errors:

            This example is not a doctest because doctests spoof sys.stdout.
            try:
                command_args = ['python', '-c', 'not python code']
                kwargs = {'stdout': sys.stdout, 'stderr': sys.stderr}
                process = background(*command_args, **kwargs)
                wait_child(process)
            except Exception as exc:
                print(exc)

        The caller can simply ignore the return value, poll() for when
        the command finishes, wait() for the command, or communicate()
        with it.

        Do not use subprocess.Popen.wait(). Use solidlibs.os.command.wait().

        >>> program = background('sleep', '0.5')

        >>> print('before')
        before

        >>> wait_child(program)

        >>> print('after')
        after

    '''
    
    _init_log()

    log.debug(f'background command_args: {command_args}')

    if not command_args:
        raise ValueError('missing command_args')

    command_args = list(map(str, command_args))

    # if there is a single string arg with a space, it's a command line string
    if len(command_args) == 1 and isinstance(command_args[0], str) and ' ' in command_args[0]:
        # run() is better able to add quotes correctly when each arg is separate
        command_args = shlex.split(command_args[0])

    kwargs_str = ''
    for key in kwargs:   # pylint: disable=consider-using-dict-items
        if kwargs_str:
            kwargs_str = kwargs_str + ', '
        kwargs_str = kwargs_str + f'{key}={kwargs[key]}'

    try:
        process = subprocess.Popen(command_args, **kwargs)

    except OSError as ose:
        log.debug(f'os error: command: {command_args}')
        log.debug(f'os error: kwargs: {kwargs_str}')
        log.exception()

        if ose.strerror:
            if 'Exec format error' in ose.strerror:
                # if the program file starts with '#!' retry with 'shell=True'.
                program_file = command_args[0]
                with open(program_file) as program:
                    first_chars = program.read(2)
                    if str(first_chars) == '#!':
                        process = subprocess.Popen(command_args, shell=True, **kwargs)

                    else:
                        log.debug(f'no #! in {program_file}')
                        raise

            else:
                raise

        else:
            raise

    except Exception as e:
        log.debug(f'command: {command_args}')
        log.debug(f'kwargs: {kwargs_str}')
        log.debug(e)
        raise

    else:
        log.debug(f"background process started: \"{' '.join(process.args)}\", pid: {process.pid}")
        return process

def get_run_args(*command_args, **kwargs):
    '''
        Get the args in list with each item a string.

        >>> _init_log()

        >>> from tempfile import gettempdir
        >>> command_args = ['ls', '-l', gettempdir()]
        >>> kwargs = {}
        >>> get_run_args(*command_args, **kwargs)
        (['ls', '-l', '/tmp'], {})

        >>> # test command line with glob=False
        >>> tmpdir = gettempdir()
        >>> command_args = ['ls', '-l', f'{gettempdir()}/solidlibs*']
        >>> kwargs = {'glob': False}
        >>> get_run_args(*command_args, **kwargs)
        (['ls', '-l', '/tmp/solidlibs*'], {})
    '''

    if kwargs is None:
        kwargs = {}

    if 'interactive' in kwargs:
        if kwargs['interactive']:
            kwargs.update(dict(stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE))
        del kwargs['interactive']

    if 'glob' in kwargs:
        globbing = kwargs['glob']
        del kwargs['glob']
    else:
        globbing = True

    # subprocess.run() wants strings
    args = []
    for arg in command_args:
        arg = str(arg)

        # see if the arg contains an inner string so we don't mistake that inner string
        # containing any wildcard chars. e.g., arg = '"this is an * example"'
        encased_str = ((arg.startswith('"') and arg.endswith('"')) or
                       (arg.startswith("'") and arg.endswith("'")))

        if ('*' in arg or '?' in arg):
            if globbing and not encased_str:
                args.extend(glob(arg))
                log(f'globbed: {arg}')
            else:
                args.append(arg)
        else:
            args.append(arg)

    return args, kwargs

def format_output(result):
    '''
        Format the output from a run().

        >>> try:
        ...     result = run('false')
        ... except subprocess.CalledProcessError as error:
        ...     pass

        >>> try:
        ...     result = run('non-existent-command')
        ... except FileNotFoundError as error:
        ...     pass
        ... else:
        ...     print('Warning: non-existent-command exists')
    '''

    if (isinstance(result, subprocess.CompletedProcess) or
        isinstance(result, subprocess.CalledProcessError)):

        result.stderrout = None

        if result.stderr is not None:
            if not isinstance(result.stderr, str):
                result.stderr = result.stderr.decode()
            if result is subprocess.CompletedProcess:
                # get a full trace
                result.stderr = format_exc() + result.stderr
            result.stderr = result.stderr.strip()
            result.stderrout = result.stderr

        if result.stdout is not None:
            if not isinstance(result.stdout, str):
                result.stdout = result.stdout.decode()
            result.stdout = result.stdout.strip()
            if result.stderr:
                result.stderrout = result.stderr + result.stdout
            else:
                result.stderrout = result.stdout

    # log(f'in format_output() result.stderrout: {result.stderrout}')
    return result

def handle_run_error(command_args, cpe):
    '''
        Handle an error from run().
    '''

    command_str = ' '.join(list(map(str, command_args)))
    log(f'command failed. "{command_str}", returncode: {cpe.returncode}')
    log(f'cpe: {cpe}')
    try:
        log(f'cpe stderr and stdout: {cpe.stderrout}')
    except AttributeError:
        pass
    log(cpe) # DEBUG

    cpe = update_stderrout(cpe)

    return cpe

def update_stderrout(result):
    ''' Convert stdout and stderrtostrings. Add stderrout. '''

    result.stderrout = None

    if result.stderr is not None:
        if not isinstance(result.stderr, str):
            result.stderr = result.stderr.decode()
        result.stderr = result.stderr.strip()
        result.stderrout = result.stderr

    if result.stdout is not None:
        if not isinstance(result.stdout, str):
            result.stdout = result.stdout.decode()
        result.stdout = result.stdout.strip()
        if result.stderr:
            result.stderrout = result.stderr + result.stdout
        else:
            result.stderrout = result.stdout

    return result

def nice(*args, **kwargs):
    ''' Run a command line at low priority, for both cpu and io.

        This can greatly increases responsiveness of the user interface.

        nice() effective prefixes the command with::

            nice nice ionice -c 3 ...

        In Debian 10 "buster" ionice must be applied on the command line
        immediately before the executable task. This means our 'nicer'
        and 'ionicer' bash scripts don't work. nice() does.

        Because ionice must be used immediately before the executable
        task, commands like this won't work as expected::

            nice('bash', 'tar', 'cvf', 'test.tar', gettempdir())

        In this case only 'bash' will get the effect of nice(), not 'tar'.

        #>>> shared_host = nice('this-is-sharedhost')
        #>>> shared_host.stderr
        #''
        #>>> print('sharedhost' in shared_host.stdout)
        #True
    '''

    args = nice_args(*args)
    return run(*args, **kwargs)

def nice_args(*args):
    ''' Modify command to run at low priority. '''

    nice_params = ('nice', 'nice', 'ionice', '--class', '3')
    return nice_params + args

def wait_child(process):
    ''' Wait for a background process to finish.

        >>> process = background('sleep', '0.5')

        >>> print('before')
        before

        >>> wait_child(process)

        >>> print('after')
        after
    '''

    if not isinstance(process, subprocess.Popen):
        raise ValueError('program must be an instance of subprocess.Popen')

    # options "should be 0 for normal operation"
    os.waitpid(process.pid, 0)

def _init_log():
    ''' Initialize log. '''

    global log

    if log is None:
        # log import delayed to avoid recursive import.
        from solidlibs.python.log import Log    # pylint: disable=import-outside-toplevel
        log = Log()

def echo(*args, **kwargs):
    '''
        Send program's stdout and stderr to the console.
        This also handles unicode encoded bytestreams better

        Currently unused. Apparently subprocess.pOpen() is not as docced.

        This does not work:
            from solidlibs.os.command import echo
            echo('ls', '/')
    '''


    class CompletedProcessStub:
        pass

    """ from subprocess docs:
    p1 = subprocess.Popen(["dmesg"], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(["grep", "hda"], stdin=p1.stdout, stdout=subprocess.PIPE)
    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    output = p2.communicate()[0]
    """
    p1 = subprocess.Popen(args, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(['echo'], stdin=p1.stdout, stdout=subprocess.PIPE)
    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    output, error = p2.communicate()

    """
    kwargs['stdout'] = subprocess.PIPE
    kwargs['stderr'] = subprocess.PIPE

    proc = subprocess.Popen(args,
                            **kwargs)

    # get streams
    # (get strings if kwargs['text']=True)
    stdout_pipe, stderr_pipe = proc.communicate()
    log(f'type(stdout_pipe): {type(stdout_pipe)}') # DEBUG

    # stderr to the console's stdout
    stderr_text = ''
    err_data = proc.stderr.readline()
    while err_data:
        line = err_data.decode()
        stderr_text = stderr_text + line
        # lines already have a newline
        print(line, end='')
        err_data = proc.stderr.readline()


    result = CompletedProcessStub()
    result.resultcode = proc.wait()
    result.stdout = proc_stdout
    result.stderr = stderr_text
    """

if __name__ == "__main__":
    import doctest
    doctest.testmod()
