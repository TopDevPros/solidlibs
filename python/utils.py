'''
    Python programming utilities.

    Utility classes and functions. Mostly utiities about python,
    not just in python.

    This module also holds code that hasn't been categorized into
    other packages. For example, many functions could go in
    solidlibs.os.fs.

    Copyright 2009-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import bz2
import doctest
import gzip as gz
import io
import os
import os.path
import string
import re
import sys
import traceback
import unicodedata
import zipfile
from contextlib import contextmanager
from fnmatch import fnmatch
from glob import glob
from subprocess import CalledProcessError
from traceback import format_exception


# linux allows almost any characters, but this is cross platform pathnames
valid_pathname_chars = f"-_.()/\\: {string.ascii_letters}{string.digits}"
version = sys.version_info[0]

global log
log = None


def is_string(obj):
    '''
        Return True iff obj is a string.

        >>> is_string('test')
        True
    '''

    return isinstance(obj, str)

def is_list(obj):
    '''
        Return True iff obj is a list.

        >>> is_list([])
        True
    '''

    log_message(type(obj))
    return isinstance(obj, list)


def is_tuple(obj):
    '''
        Return True iff obj is a tuple.

        >>> is_string('test')
        True
    '''

    return isinstance(obj, tuple)

def is_dict(obj):
    '''
        Return True iff obj is a dictionary.

        >>> is_string('test')
        True
    '''

    return isinstance(obj, dict)

def say(message):
    ''' Speak a message.

        Runs a "say" program, passing the message on the command line.
        Because most systems are not set up for speech, it is not an
        error if the "say" program is missing or fails.

        It is often easy to add a "say" program to a system. For example,
        a linux system using festival for speech can use a one line script:
            festival --batch "(SayText \"$*\")"

        Depending on the underlying 'say' command's implementation, say()
        probably does not work unless user is in the 'audio' group.

        >>> say('test say')
        '''

    enabled = True

    if enabled:
        try:
            from solidlibs.os import command
            # the words are unintelligible, and usually all we want is to know something happened
            # message = 'tick' # just a sound #DEBUG
            # os.system passes successive lines to sh
            message = message.split('\n')[0]
            command.run('say', *message)
        except:   # pylint:bare-except -- catches more than "except Exception"
            pass

def generate_password(max_length=25, punctuation_chars='-_ .,!+?$#'):
    '''
        Generate a password.

        >>> len(generate_password())
        25
    '''

    # the password must be random, but the characters must be valid for django
    password = ''
    while len(password) < max_length:
        new_char = os.urandom(1)
        try:
            new_char = new_char.decode()
            # the character must be a printable character
            if ((new_char >= 'A' and new_char <= 'Z') or
                (new_char >= 'a' and new_char <= 'z') or
                (new_char >= '0' and new_char <= '9') or
                (new_char in punctuation_chars)):

                # and the password must not start or end with a punctuation
                if (new_char in punctuation_chars and
                    (len(password) == 0 or (len(password) + 1) == max_length)):
                    pass
                else:
                    password += new_char
        except:   # pylint:bare-except -- catches more than "except Exception"
            pass

    return password

def clean_pathname(pathname):
    ''' Clean a pathname by removing all invalid chars.

        See http://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-pathname-in-python
        From that page, roughly:

            The unicodedata.normalize call replaces accented characters
            with the unaccented equivalent, which is better than simply
            stripping them out. After that all disallowed characters are
            removed. Doesn't avoid possible disallowed pathnames."
    '''

    ascii_pathname = unicodedata.normalize('NFKD', pathname.decode()).encode('ASCII', 'ignore')
    return ''.join(c for c in ascii_pathname if c in valid_pathname_chars)


def strip_spaces_and_blank_lines(data):
    '''
        Strip leading and trailing spaces plus blank lines.

        >>> data = "  This is the first line.  \\n   \\n\\n This is the second line.\\n"
        >>> strip_spaces_and_blank_lines(data)
        'This is the first line.\\nThis is the second line.\\n'
    '''

    try:
        if data is not None:
            new_data = []
            for line in data.split('\n'):
                line = trim(line, ' ').decode()
                if len(line.strip('\n')) > 0:
                    new_data.append(f'{line}\n')

            data = ''.join(new_data)
    except:   # pylint:bare-except -- catches more than "except Exception"
        log_message(format_exc())

    return data

def ltrim(string, prefix):
    ''' Trim all prefixes from string. '''

    length = len(prefix)
    while string.startswith(prefix):
        string = string[length:]
    return string

def rtrim(string, suffix):
    ''' Trim all suffixes from string. '''

    length = len(suffix)
    while string.endswith(suffix):
        string = string[:-length]
    return string

def trim(string, xfix):
    ''' Trim all prefixes or suffixes of xfix from string. '''

    if is_string(string):
        string = string.encode()
    if is_string(xfix):
        xfix = xfix.encode()

    length = len(xfix)
    while string.startswith(xfix):
        string = string[length:]
    while string.endswith(xfix):
        string = string[:-length]
    return string

def remove_lines(string, count):
    ''' Remove lines from string.

        If count is negative, removes lines from end of string. '''

    if count > 0:
        string = '\n'.join(string.split('\n')[count:])
    elif count < 0:
        string = '\n'.join(string.split('\n')[:count])
    return string

def pathmatch(path, pattern):
    ''' Test whether the path matches the pattern.

        This is a mess that needs to be replaced with an ant-style path match.

        The pattern is a shell-style wildcard, not a regular expression.
        fnmatch.fnmatch tests filenames, not paths.

        '**' at the beginning of a pattern matches anything at the beginning
        of a path, but no other wildcards are allowed in the pattern. '''

    def split(path):
        path = os.path.expanduser(path)
        path = os.path.abspath(path)
        return path.split('/')

    if pattern.startswith('**'):
        result = path.endswith(pattern[2:])

    else:
        path = split(path)
        pattern = split(pattern)
        result = (len(path) == len(pattern) and
            all(fnmatch(path[i], pattern[i]) for i in range(len(path))))

    return result

def resolve_path(path):
    ''' Resolves file path wildcards, links, and relative directories.

        To resolve a wildcard path that matches more than one file, use
        glob() and pass each result to resolve_path().

        Returns None if wildcard does not match any files. Raises
        ValueError if wildcard matches more than one file. '''

    paths = glob(path)
    if paths:
        if len(paths) > 1:
            raise ValueError(f'Matches more than one path: {path}')
            path = os.path.normpath(os.path.realpath(paths[0]))
    else:
        path = None
    return path

def domain_base(domain):
    ''' Returns base name from domain.

        I.e. base.tld or base.co.countrydomain or base.com.countrydomain
        all have the same base name.

        E.g. google.com, google.bg, google.de, google.co.in all are based
        on google.

        This can be fooled by domain spoofers or squatters.

        >>> domain_base('example.com')
        'example'
    '''

    if type(domain) is bytes:
        domain = domain.decode()
    # regexes might be clearer (or not) but would be slower
    parts = domain.split('.')
    if len(parts) > 1:
        # toss the top level domain
        parts = parts[:-1]
        if len(parts) > 1:
            # toss generic second level domains
            if parts[-1] in ['com', 'co', 'org', 'net']:
                parts = parts[:-1]
    # top level left is the base name
    return parts[-1]

class textfile(object):
    ''' Open possibly gzipped text file as file using contextmanager.

        E.g. "with textfile('mytext.gz') as f".

        Avoids "AttributeError: GzipFile instance has no attribute '__exit__'"
        prior to Python 3.1.

        As of Python 2.6 contextlib.closing() doesn't work. It doesn't expose underlying
        gzip functions because its __enter__() returns the inner object, and it has no
        __getattr__()
        to expose the inner gzip.open(). '''

    def __init__(self, filename, rwmode='r'):
        if filename.endswith('.gz'):
            self.f = gz.open(filename, f'{rwmode}b')
        elif filename.endswith('.bz2'):
            self.f = bz2.BZ2File(filename, f'{rwmode}b')
        elif filename.endswith('.zip'):
            self.f = zipfile.ZipFile(filename, f'{rwmode}b')
        else:
            self.f = open(filename, rwmode)
        self.opened = True

    def __iter__(self):
        return iter(self.f)

    def __enter__(self):
        return self.f

    def __exit__(self, *exc_info):
        self.close()

    def unused_close(self):
        if self.opened:
            self.f.close()
            self.opened = False

    def __getattr__(self, name):
        return getattr(self.f, name)

def gzip(uncompressed):
    ''' Gzip a string '''

    compressed_fileobj = StringIO()
    with gz.GzipFile(fileobj=compressed_fileobj, mode='w') as f:  #, compresslevel=5) as f:
        f.write(uncompressed)
    return compressed_fileobj.getvalue()

def gunzip(compressed):
    ''' Gunzip a string '''

    compressed_fileobj = StringIO(compressed)
    with gz.GzipFile(fileobj=compressed_fileobj, mode='r') as f:
        uncompressed = f.read()
    return uncompressed

def different(file1, file2):
    ''' Returns whether the files are different. '''

    # diff succeeds if there is a difference, and fails if no difference
    try:
        from solidlibs.os import command
        command.run('diff', file1, file2, brief=True)
        different = False

    except CalledProcessError:
        different = True

    return different

def slugify(value):
    ''' Converts string to a form usable in a url withjout encoding.

        Strips white space from ends, converts to lowercase,
        converts spaces to hyphens, and removes non-alphanumeric characters.
    '''
    value = value.strip().lower()
    value = re.sub('[\s-]+', '-', value)

    newvalue = ''
    for c in value:
        if (
              (c >= 'A' and c <= 'Z') or
              (c >= 'a' and c <= 'z') or
              (c >= '0' and c <= '9') or
              c == '-' or
              c == '_'
              ):
            newvalue += c
    return newvalue

def replace_strings(text, replacements, regexp=False):
    """ Replace text. Returns new text.

        'replacements' is a dict of {old: new, ...}.
        Every occurence of each old string is replaced with the
        matching new string.

        If regexp=True, the old string is a regular expression.

        >>> text = 'ABC DEF 123 456'
        >>> replacements = {
        ...     'ABC': 'abc',
        ...     '456': 'four five six'
        ... }
        >>> replace_strings(text, replacements)
        'abc DEF 123 four five six'
    """

    for old in replacements:
        new = replacements[old]
        if regexp:
            text = re.sub(old, new, text)
        else:
            text = text.replace(old, new)
    return text

def delete_empty_files(directory):
    ''' Delete empty files in directory.

        Does not delete any subdirectories or files in them.

        >>> from tempfile import mkdtemp, mkstemp
        >>> directory = mkdtemp()
        >>> assert os.path.isdir(directory)
        >>> handle, filename1 = mkstemp(dir=directory)
        >>> os.close(handle)
        >>> assert os.path.exists(filename1)
        >>> handle, filename2 = mkstemp(dir=directory)
        >>> os.close(handle)
        >>> assert os.path.exists(filename2)
        >>> with open(filename2, 'w') as f2:
        ...     len = f2.write('data')
        >>> delete_empty_files(directory)
        >>> assert not os.path.exists(filename1)
        >>> assert os.path.exists(filename2)
        >>> os.remove(filename2)
        >>> assert not os.path.exists(filename2)
        >>> os.rmdir(directory)
        >>> assert not os.path.isdir(directory)
    '''

    wildcard = os.path.join(directory, '*')
    for filename in glob(wildcard):
        if os.path.getsize(filename) <= 0:
            os.remove(filename)

def randint(min=None, max=None):
    ''' Get a random int.

        random.randint() requires that you specify the min and max of
        the integer range for a random int. But you almost always want
        the min and max to be the system limits for an integer.
        If not use random.randint().

        'min' defaults to system minimum integer.
        'max' defaults to system maximum integer.
    '''

    import random

    maxsize = sys.maxsize

    if min is None:
        min = -(maxsize-1)
    if max is None:
        max = maxsize

    return random.randint(min, max)

def strip_youtube_hash(filename):
    ''' Strip youtube hash from end of filename '''

    if '.' in filename:
        rootname, _, extension = filename.rpartition('.')
        youtube_match = re.match(r'(.*)-[a-zA-Z0-9\-_]{11}$', rootname)
        if youtube_match:
            cleanroot = youtube_match.group(1)
            filename = cleanroot + '.' + extension
    return filename

def simplify_episode_filename(filename):
    ''' Strip junk from end of tv episode filename '''

    if '.' in filename:
        rootname, _, extension = filename.rpartition('.')
        cleanroot = re.sub(r'(.*)[Ss](\d\d)[Ee](\d\d).*', r'\1S\2E\3', rootname)
        filename = cleanroot + '.' + extension
    return filename

def last_exception(noisy=False):
    ''' Returns a printable string of the last exception.

        If noisy=True calls say() with last_exception_only(). '''

    if noisy:
        say(last_exception_only())
    return traceback.format_exc()

def last_exception_only():
    ''' Returns a printable string of the last exception without a traceback. '''

    type, value, traceback = sys.exc_info()
    if type:
        s = str(type).split('.')[-1].strip('>').strip("'")
        if value is not None and len(str(value)):
            s += f': {value}'
    else:
        s = ''
    return s

def last_exception(noisy=False):
    ''' Returns a printable string of the last exception.

        If noisy=True calls say() with last_exception_only(). '''

    if noisy:
        say(last_exception_only())
    return traceback.format_exc()

def last_exception_only():
    ''' Returns a printable string of the last exception without a traceback. '''

    type, value, traceback = sys.exc_info()
    if type:
        s = str(type).split('.')[-1].strip('>').strip("'")
        if value is not None and len(str(value)):
            s += f': {value}'
    else:
        s = ''
    return s

def stacktrace():
    '''
        Returns a printable stacktrace.

        Contrary to the python docs, python often limits the number of
        frames in a stacktrace. This is a full stacktrace.

        >>> text = stacktrace()
        >>> assert text.strip().startswith('Traceback ')
        >>> assert 'utils.py' in text
    '''

    s = io.StringIO()
    s.write('Traceback (most recent call last):\n')
    traceback.print_stack(file=s)
    return s.getvalue()

def object_name(obj, include_repr=False):
    ''' Get a human readable type name of a module, function, class, class method, or instance.

        The name is not guaranteed to be unique.

        If include_repr is True, an instance has its string representation appended.

        >>> import datetime
        >>> object_name(datetime.date)
        'datetime.date'

        >>> object_name('test string')
        'builtins.str instance'

        >>> class TestClass():
        ...     pass
        >>> name =object_name(TestClass)
        >>> name == 'solidlibs.python.utils.TestClass' or name == '__main__.TestClass'
        True
        >>> inst = object_name(TestClass())
        >>> inst == 'solidlibs.python.utils.TestClass instance' or inst == '__main__.TestClass instance'
        True

        To do: Consider using 'inspect' module.
    '''

    #package_name = getattr(obj, '__package__', None)
    module_name = getattr(obj, '__module__', None)
    local_object_name = getattr(obj, '__name__', None)

    """
    log_message(f'obj: {obj}, type(obj): {type(obj)}') #DEBUG
    log_message(f'initial package_name: {package_name}, type(package_name): {type(package_name)}') #DEBUG
    log_message(f'initial module_name: {module_name}, type(module_name): {type(module_name)}') #DEBUG
    log_message(f'initial local_object_name: {local_object_name}, type(local_object_name): {type(local_object_name)}') #DEBUG
    """

    name = None

    if module_name and local_object_name:
        name = f'{module_name}.{local_object_name}'

    elif local_object_name:
        name = local_object_name

    else:
        class_obj = getattr(obj, '__class__', None)
        class_module_name = getattr(class_obj, '__module__', None)
        local_object_name = getattr(class_obj, '__name__', None)

        """
        log_message(f'obj.__class__: {obj.__class__}, type(obj.__class__): {type(obj.__class__)}') #DEBUG
        log_message(f'class_obj: {class_obj}, type(class_obj): {type(class_obj)}') #DEBUG
        log_message(f'class_module_name: {class_module_name}, type(class_module_name): {type(class_module_name)}') #DEBUG
        log_message(f'local_object_name: {local_object_name}, type(local_object_name): {type(local_object_name)}') #DEBUG
        """

        name = f'{class_module_name}.{local_object_name} instance'
        if include_repr:
            name = f'{name}: {repr(obj)}'

    return name

def run_file_test(python_pathname, **kwargs):
    ''' Run doctests in specifed python source file. '''

    # you need both report=True and raise_on_error=True if you want to see the errors from a doctest
    failure_count, test_count = doctest.testfile(python_pathname, report=True, raise_on_error=True, **kwargs)
    try:
        assert failure_count == 0
    except AssertionError:
        error_message = f'File {python_pathname}: Failed {failure_count} of {test_count} tests'
        log_message(error_message)
        log_message(error_message)

def run_module_test(module):
    ''' Run doctests in specified module. '''

    # you need both report=True and raise_on_error=True
    # if you want errors from a doctest to be sent to stderr
    failure_count, test_count = doctest.testmod(module, report=True, raise_on_error=True)
    try:
        assert failure_count == 0
        error_message = None
    except AssertionError:
        error_message = f'Module {module}: Failed {failure_count} of {test_count} tests'
        log_message(error_message)
        log_message(error_message)

    return test_count, error_message

def log_message(message):
    '''
        Print the message because we cannot
        use solidlibs.python.log in this module
    '''
    _debug = False
    if _debug:
        print(msg)

@contextmanager
def chdir(dirname=None):
    ''' Chdir contextmanager that restores current dir.

        From http://www.astropython.org/snippet/2009/10/chdir-context-manager

        This context manager restores the value of the current working
        directory (cwd) after the enclosed code block completes or
        raises an exception.  If a directory name is supplied to the
        context manager then the cwd is changed prior to running the
        code block.
    '''

    curdir = os.getcwd()
    try:
        if dirname is not None:
            os.chdir(dirname)
        yield
    finally:
        os.chdir(curdir)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
