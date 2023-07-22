'''
    Low level python functions you probably never need..

    This module also holds code that hasn't been categorized into
    other packages. For example, many functions could go in
    solidlibs.os.fs.

    Copyright 2009-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import importlib
import locale
import os
import os.path
import string
import re
import sys
import trace
import traceback
import types
from contextlib import contextmanager
from io import StringIO
from urllib.parse import urlparse
from tempfile import gettempdir

global log
log = None


class NotImplementedException(Exception):
    ''' Operation not implemented exception. '''
    pass


class MovedPermanentlyException(Exception):
    ''' Object moved permanently exception.

        Always say where it was moved. '''
    pass


def dynamically_import_module(name):
    '''
        Dynamically import a module. See python docs on __import__()

        >>> module_str = str(dynamically_import_module('solidlibs.python'))
        >>> module_str.startswith("<module 'solidlibs.python' from ")
        True
        >>> module_str.endswith("solidlibs/python/__init__.py'>")
        True
     '''

    module = __import__(name)
    components = name.split('.')
    for component in components[1:]:
        module = getattr(module, component)
    return module

def dynamic_import(name):
    '''
        >>> module_str = str(dynamic_import('solidlibs.python'))
        >>> module_str.startswith("<module 'solidlibs.python' from ")
        True
        >>> module_str.endswith("solidlibs/python/__init__.py'>")
        True
    '''
    # from Python Library Reference, Built-in Functions, __import__
    mod = __import__(name)
    components = name.split('.')
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod

def print_imported_modules(filename):
    ''' Print modules imported by filename.

        Warning: Runs filename.

        >>> # how do we test this? how we generally use it:
        >>> # print_imported_modules(__file__)
    '''

    import modulefinder

    if filename.endswith('.pyc') or filename.endswith('.pyo'):
        filename = filename[:-1]
    print(filename)

    finder = modulefinder.ModuleFinder()
    finder.run_script(filename)

    # See /usr/share/doc/python2.7/html/library/modulefinder.html
    print('Loaded modules:')
    for name in sorted(finder.modules.keys()):
        mod = finder.modules[name]
        print(f'    {name}: {mod}')
        globalnames = list(mod.globalnames.keys())
        modules = sorted(globalnames[:3])
        print(','.join(modules))

    print('Modules not imported:')
    keys = finder.badmodules.keys()
    for name in keys:
        print(f'    {name}')

def caller_id(ignore=None):
    ''' Return standard caller id string. '''

    filename, line = caller(ignore=ignore)
    return f'{filename}:{line}'

def caller(ignore=None, this_module_valid=False):
    ''' Returns (filename, linenumber) of the caller.

        To ignore calls from the current module::
            filename, line = caller(ignore=[__file__])
        This could conceivably ignore extra files if __file__ contains '.' etc.

        If this function is called from this module, set this_module_valid=True.
    '''

    def ignore_filename(filename):
        ''' Ignore files in ignore list and runpy.py. '''

        ignored = False
        if filename.endswith('/runpy.py'):
            ignored = True
        else:
            for pattern in _ignore:
                if re.match(pattern, filename):
                    ignored = True

        return ignored

    if ignore:
        _ignore = ignore
    else:
        _ignore = []
    # ignore solidlibs.python.internals unless this_module_valid=True
    if not this_module_valid:
        _ignore = _ignore + [__file__]

    call_line = None

    stack = list(traceback.extract_stack())
    stack.reverse()
    for filename, linenumber, _, _ in stack:
        if not call_line:
            if not ignore_filename(filename):
                __, __, filename = filename.rpartition('/') # DEBUG
                call_line = (filename, linenumber)

    return call_line

def caller_module_name(ignore=None, this_module_valid=False):
    ''' Get the caller's fully qualified module name.

        If this function is called from this module, set this_module_valid=True.

        To do: Test linked package dirs in parent dirs.

        To get the parent caller instead of the module that actually
        calls caller_module_name():

            name = caller_module_name(ignore=[__file__])

        >>> # this code really needs to be tested from a different module
        >>> name = caller_module_name(this_module_valid=True)
        >>> name.endswith('internals')
        True
        >>> name = caller_module_name(ignore=[__file__], this_module_valid=True)
        >>> 'caller_module_name' in name
        True
    '''

    def ignore_filename(filename):
        ''' Ignore files in ignore list and runpy.py. '''

        if _debug_caller_module_name: print(f'in ignore_filename() ignore: {repr(ignore)}') #DEBUG
        return (filename in ignore) or filename.endswith('/runpy.py')

    def is_python_module_dir(dirname):
        # a python module dir has an __init__.py file
        init_path = os.path.join(dirname, '__init__.py')
        return os.path.exists(init_path)

    def strip_py(filename):
        if filename.endswith('.py'):
            filename, _, _ = filename.rpartition('.')
        return filename

    _debug_caller_module_name = False

    if _debug_caller_module_name: print(f'ignore: {repr(ignore)}') #DEBUG

    # make ignore list
    if ignore:
        _ignore = ignore
    else:
        _ignore = []
    # ignore solidlibs.python.internals unless this_module_valid=True
    if not this_module_valid:
        _ignore = _ignore + [__file__]
    # make stack and __file__ filenames match
    ignore = []
    for filename in _ignore:
        # the ignore=[...] param is usually ignore=[__file__]
        # stack filenames end in .py; __file__ filenames end in .pyc or .pyo
        # make them all .py
        basename, _, extension = filename.rpartition('.')
        if extension == 'pyc' or extension == 'pyo':
            filename = basename + '.py'
        ignore.append(filename)

    name = None

    if _debug_caller_module_name:
        print('caller_module_name traceback.extract_stack():') #DEBUG
        for stack_item in traceback.extract_stack():
            print(f'    {stack_item}') #DEBUG

    stack = list(traceback.extract_stack())
    stack.reverse()
    # filename, line number, function name, text
    for filename, _, _, _ in stack:

        if not name:
            if ignore_filename(filename):
                if _debug_caller_module_name: print(f'caller_module_name ignored filename: {filename}') #DEBUG

            else:
                if _debug_caller_module_name: print(f'caller_module_name filename: {filename}') #DEBUG
                # find python module dirs in filename
                modules = []
                dirname, _, basename = filename.rpartition('/')
                while dirname and is_python_module_dir(dirname):
                    #if _debug_caller_module_name: print(f'caller_module_name is_python_module_dir: {dirname}') #DEBUG
                    modules.append(os.path.basename(dirname))
                    dirname, _, _ = dirname.rpartition('/')
                modules.reverse()

                # if the filename is a __main__.py for a package, just use the package name
                if basename != '__main__.py':
                    modules.append(strip_py(basename))
                #if _debug_caller_module_name: print(f'caller_module_name modules: {repr(modules))}' #DEBUG

                name = '.'.join(modules)

    if _debug_caller_module_name: print(f'caller_module_name: {name}') #DEBUG
    return name

def is_package_type(object):
    '''
        Returns True if object is a python package, else False.

        >>> import solidlibs.python
        >>> is_package_type(solidlibs.python)
        True
        >>> import solidlibs.python.internals
        >>> is_package_type(solidlibs.python.internals)
        False
    '''

    # this seems to be roughly what python does internally
    return (is_module_type(object) and
        (os.path.basename(object.__file__).endswith('__init__.py') or
         os.path.basename(object.__file__).endswith('__init__.pyc') or
         os.path.basename(object.__file__).endswith('__init__.pyo')))

def is_module_type(object):
    ''' Returns True if object is a python module, else False.

        Convenience function for symmetry with is_package_type().

        >>> import solidlibs.python
        >>> is_module_type(solidlibs.python)
        True
        >>> import solidlibs.python.internals
        >>> is_module_type(solidlibs.python.internals)
        True
    '''

    return isinstance(object, types.ModuleType)

def is_instance(obj, cls):
    '''
        More reliable version of python builtin isinstance()

        >>> is_instance('solidlibs.python', str)
        True
    '''

    log_message(f'is_instance(obj={obj}, cls={cls})')
    log_message(f'is_instance() type: obj={type(obj)}, cls={type(cls)}')
    try:
        mro = obj.__mro__
    except AttributeError:
        mro = type(obj).__mro__
    log_message(f'is_instance() mro: {mro}')
    match = cls in mro

    log_message(f'is_instance() match: {match}')
    return match

def is_class_instance(obj):
    ''' Returns whether the object is an instance of any class.

        You can't reliably detect a class instance with

            isinstance(obj, types.InstanceType)

        as of Python 2.6 2013-05-02. The types module only handles old style
        python defined classes, so types.InstanceType only detects instances
        of the same style.

        >>> import datetime
        >>> c_style_class_instance = datetime.date(2000, 12, 1)
        >>> is_class_instance(c_style_class_instance)
        True

        >>> class OldStyleClass:
        ...     class_data = 27
        ...
        ...     def __init__(self):
        ...         self.instance_data = 'idata'

        ...     def instance_function(self):
        ...         return 3
        >>> old_c = OldStyleClass()
        >>> is_class_instance(old_c)
        True

        >>> class NewStyleClass(object):
        ...     class_data = 27
        ...
        ...     def __init__(self):
        ...         self.instance_data = 'idata'

        ...     def instance_function(self):
        ...         return 3
        >>> new_c = NewStyleClass()
        >>> is_class_instance(new_c)
        True

        >>> # base types are not instances
        >>> is_class_instance(2)
        False
        >>> is_class_instance([])
        False
        >>> is_class_instance({})
        False

        >>> # classes are not instances
        >>> is_class_instance(datetime.date)
        False
        >>> is_class_instance(OldStyleClass)
        False
        >>> is_class_instance(NewStyleClass)
        False

        >>> # test assumptions and python imlementation details

        >>> t = type(2)
        >>> str(t) == "<class 'int'>"
        True
        >>> t = type([])
        >>> str(t) == "<class 'list'>"
        True
        >>> t = type({})
        >>> str(t) == "<class 'dict'>"
        True

        >>> cls = getattr(2, '__class__')
        >>> str(cls) == "<class 'int'>"
        True
        >>> superclass = getattr(cls, '__class__')
        >>> str(superclass) == "<class 'type'>"
        True

        >>> t = str(type(datetime.date))
        >>> t == "<class 'type'>"
        True
        >>> t = str(type(c_style_class_instance))
        >>> t == "<class 'datetime.date'>"
        True
        >>> t = repr(datetime.date)
        >>> t == "<class 'datetime.date'>"
        True
        >>> repr(c_style_class_instance)
        'datetime.date(2000, 12, 1)'
        >>> isinstance(c_style_class_instance, types.MethodType)
        False
        >>> hasattr(c_style_class_instance, '__class__')
        True
        >>> '__dict__' in dir(c_style_class_instance)
        False
        >>> cls = c_style_class_instance.__class__
        >>> hasattr(cls, '__class__')
        True
        >>> '__dict__' in dir(cls)
        False
        >>> hasattr(cls, '__slots__')
        False
        >>> cls = getattr(c_style_class_instance, '__class__')
        >>> str(cls) == "<class 'datetime.date'>"
        True
        >>> superclass = getattr(cls, '__class__')
        >>> str(superclass) == "<class 'type'>"
        True

        >>> ok = '__dict__' in dir(old_c)
        >>> ok == True
        True
        >>> hasattr(old_c, '__slots__')
        False

        >>> '__dict__' in dir(new_c)
        True
        >>> hasattr(new_c, '__slots__')
        False

        '''

    type_str = str(type(obj))

    # old style python defined classes
    if type_str == "<class 'instance'>":
        is_instance = True

    # C defined classes
    elif type_str.startswith('<class '):
        # base types don't have a dot
        is_instance =  '.' in type_str

    # new style python defined classes
    elif type_str.startswith('<'):
        # if it has an address, it's an instance, not a class
        is_instance =  ' 0x' in repr(obj)

    else:
        is_instance = False

    return is_instance

    """ does not detect c-style classes e.g. datetime.xyz
    def is_old_style_instance(obj):
        return isinstance(obj, types.InstanceType)

    def is_new_style_instance(obj):
        # http://stackoverflow.com/questions/14612865/how-to-check-if-object-is-instance-of-new-style-user-defined-class
        is_instance = False
        if hasattr(obj, '__class__'):
            cls = obj.__class__
            if hasattr(cls, '__class__'):
                is_instance = ('__dict__' in dir(cls)) or hasattr(cls, '__slots__')
        return is_instance

    return is_new_style_instance(obj) or is_old_style_instance(obj)
    """

def run(sourcecode):
    '''
        Run source code text.

        >>> run('print("hi")')
        hi
    '''

    # magic. bad. but wasted too many hours trying pythonic solutions
    # in python 2.7 importlib doesn't know spec.Specs is the same as dbuild.spec.Specs

    import tempfile

    __, exec_path = tempfile.mkstemp(
        suffix='.py',
        dir=gettempdir())

    log_message(f'sourcecode:\n{sourcecode.strip()}')

    with open(exec_path, 'w') as exec_file:
        exec_file.write(sourcecode)

    try:
        exec(compile(open(exec_path).read(), exec_path, 'exec'), globals())
    finally:
        os.remove(exec_path)

def import_module(name):
    '''
        Import with debugging

        Args:
            name: Name of module to import

        Returns:
            Imported module

        >>> module_str = str(import_module("solidlibs.os.user"))
        >>> module_str.startswith("<module 'solidlibs.os.user' from ")
        True
        >>> module_str.endswith("solidlibs/os/user.py'>")
        True
    '''

    try:
        log_message(f'import_module({name})') #DEBUG
        module = importlib.import_module(name)
        log_message(f'import_module() result: {module}') #DEBUG

    except ImportError as imp_error:
        log_message(f'unable to import {name}')
        log_message('ImportError: ' + str(imp_error))
        msg = f'could not import {name}'
        log_message(msg)
        # find out why
        from solidlibs.os import command
        log_message(command.run(['python3', '-c', f'import {name}']).stderr)
        raise ImportError(msg)

    return module

def import_file(name, path):
    '''
        Import source file with debugging

        <<< module = import_file(__file__, '/usr/local/lib/python3.9/dist-packages/solidlibs/os/user.py')
        <<< print(str(module))
        <module 'python.py' from '/usr/local/lib/python3.9/dist-packages/solidlibs/os/user.py'>
    '''

    import importlib

    try:
        log_message(f'import_file({path})') #DEBUG
        # deprecated in python 3.3
        # the 'right' way to do this varies greatly with the specific python version
        # see http://stackoverflow.com/questions/19009932/import-arbitrary-python-source-file-python-3-3
        #     http://bugs.python.org/issue21436
        # the following is undocumented in python 3, and may not work in all versions
        module = importlib.find_loader(name, path)
        log_message(f'import_file() result: {module}') #DEBUG
    except ImportError as imp_error:
        log_message(f'unable to import {path}')
        log_message('ImportError: ' + str(imp_error))
        msg = f'could not import {path}'
        log_message(msg)
        raise ImportError(msg)

    return module

def get_module(name):
    ''' Get the module based on the module name.

        The module name is available within a module as __name__.

        >>> module_str = str(get_module(__name__)) # doctest: +ELLIPSIS
        >>> module_str.startswith("<module 'solidlibs.python.internals'") or module_str.startswith("<module '__main__' from")
        True
        >>> module_str.endswith("internals.py'>")
        True
    '''

    module_name = sys.modules[name]
    log_message(f'module name: {module_name}')

    return module_name

def caller_dir():
    ''' Get the caller's dir.

        This is actually the source dir for the caller of the caller of this module.
    '''

    stack = traceback.extract_stack()[:-2]
    (filename, line_number, function_name, text) = stack[0]
    return os.path.dirname(filename) or os.getcwd()

def caller_file():
    ''' Get the caller's file.

        This is actually the source file for the caller of the caller of this module.
    '''

    stack = traceback.extract_stack()[:-2]
    (filename, line_number, function_name, text) = stack[0]
    return filename

def exec_trace(code, ignoredirs=[sys.prefix, sys.exec_prefix], globals=None, locals=None, coverdir='/tmp'):
    ''' Trace code.

        Code must be a string. Code must start without leading spaces in the string.

        exec_trace() usually requires passing "globals=globals(), locals=locals()".

        Example:
            from solidlibs.python.internals import exec_trace
            exec_trace("""
from solidlibs.reinhardt.events import log_event
log_event(name, request=request, details=details)
                """,
                globals=globals(), locals=locals())
        '''

    tracer = trace.Trace(ignoredirs=ignoredirs)
    tracer.runctx(code.strip(), globals=globals, locals=locals)
    r = tracer.results()
    r.write_results(show_missing=True, coverdir=coverdir)

def pdb_break():
    ''' Breakpoint for pdb command line debugger.

    Usage:
        from solidlibs.python.internals import pdb_break ; pdb_break()
    '''

    import pdb
    log_message('breakpointing for pdb')
    pdb.set_trace()

def winpdb_break():
    ''' Breakpoint for winpdb debugger.

        Example:
            from solidlibs.python.internals import winpdb_break; winpdb_break() #DEBUG
    '''

    import rpdb2 #DEBUG
    log_message('breakpointing for winpdb')
    rpdb2.start_embedded_debugger("password") #DEBUG

def to_bytes(source, encoding=None):
    ''' Convenience method to convert to bytes. '''

    # if source is a string, encoding is required
    # in other cases it doesn't hurt
    if encoding is None:
        encoding = locale.getpreferredencoding(False)

    return bytes(source, encoding=encoding)

def get_scheme_netloc(url):
    ''' Return (scheme, netloc) from url.

        If the port is non-standard, the netloc is 'domain:port'. Otherwise
        netloc is the domain.

       This is used because python 2.4 and 2.5
       give slightly different results from urlparse.

        >>> get_scheme_netloc('http://example.com')
        ('http', 'example.com')
        >>> get_scheme_netloc('https://test:8211')
        ('https', 'test:8211')
    '''

    parsed_url = urlparse(url)

    try:
        scheme = parsed_url.scheme
        netloc = parsed_url.netloc
    except:   # pylint:bare-except -- catches more than "except Exception"
        scheme = parsed_url[0]
        netloc = parsed_url[1]

    return (scheme, netloc)

def get_remote_ip(request):
    '''Get the remote ip. If there is a forwarder, assume the first IP
       address (if there are more than 1) is the original machine's address.

       Otherwise, use the remote addr.

       Any errors, return 0.0.0.0
    '''

    Unknown_IP = '0.0.0.0'

    if request:
        try:
            # if we're using a reverse proxy, the ip is the proxy's ip address
            remote_addr = request.META.get('REMOTE_ADDR', '')
            forwarder = request.META.get('HTTP_X_FORWARDED_FOR', '')
            if forwarder and forwarder is not None and len(forwarder) > 0:
                m = re.match('(.*?),.*?', forwarder)
                if m:
                    remote_ip = m.group(1)
                else:
                    remote_ip = forwarder
            else:
                remote_ip = remote_addr

            if not remote_ip or remote_ip is None or len(remote_ip) <= 0:
                remote_ip = Unknown_IP
        except:   # pylint:bare-except -- catches more than "except Exception"
            log_message(traceback.format_exc())
            remote_ip = Unknown_IP
    else:
        remote_ip = Unknown_IP
        log_message('no request so returning unknown ip address')

    return remote_ip

def pipe(value, *fns):
    ''' Pipe data from functions a() to b() to c() to d() ...

        "pipe(x, a, b, c, d)" is more readble than "d(c(b(a(x))))".

        See http://news.ycombinator.com/item?id=3349429

        pipe() assumes every function in its list will consume and return the data.
        If you need more control such as filtering and routing, see
        the coroutine package.

        >>> def sqr(x):
        ...     return x*x

        >>> def half(x):
        ...     return x/2.0

        >>> for i in range(5):
        ...     pipe(i, sqr, half)
        0.0
        0.5
        2.0
        4.5
        8.0
    '''

    for fn in fns:
        value = fn(value)
    return value

def log_message(message):
    '''
        Print the message because we cannot
        use solidlibs.python.log in this module
    '''
    _debug = False
    if _debug:
        print(msg)

@contextmanager
def os_environ_context(environ):
    """ Context manager to restore os environment variables. """

    old_environ = dict(os.environ)
    os.environ.update(environ)

    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
