'''
    Read/write plain text files.

    This module can be replaced using python directly.
    But there are many times when you want to read and write
    simple text files without a lot of exceptions. In
    other words, if you try to read a file as lines and
    it doesn't exist, then you just get an empty list.

    Copyright 2008-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import shutil
from traceback import format_exc

from solidlibs.python.log import Log
from solidlibs.python.utils import is_string

log = Log()


def read_text(filename):
    ''' Read the contents of a text file.

        Returns: string
    '''

    return '\n'.join(read(filename))

def read(filename):
    '''Read the contents of a text file. Return the lines as a list.

       If the file doesn't exist, return empty list.
    '''

    try:
        inputFile = open(filename, 'rt')
        lines = inputFile.readlines()
        inputFile.close()
    except:   # pylint:bare-except -- catches more than "except Exception"
        log(f'Unable to read {filename}')
        log(format_exc())
        lines = []

    return lines


def write_line(filename, line, append=False):
    '''Write a line to a text file.

      Log any io errors and then raise another ioerrr.
    '''

    lines = [line]
    return write(filename, lines, append)


def write(filename, lines, append=False):
    '''Write the lines to a text file.

      Log any io errors and then raise another ioerrr.
    '''

    try:
        if append:
            method = 'at'
        else:
            method = 'wt'

        outputFile = open(filename, method)
        for line in lines:
            if isinstance(line, list):
                # line must be another list
                # let's assume there aren't any more nested lists
                for inner_line in line:
                    if is_string(l):
                        text = inner_line.decode()
                    else:
                        text = inner_line
                    outputFile.write(text)
            else:
                if is_string(line):
                    text = line
                else:
                    text = line.decode()
                outputFile.write(text)
        outputFile.close()

    except IOError:
        log(f'Unable to write {filename}')
        log(format_exc())
        raise IOError

    return lines


def backup_and_write(filename, lines, append=False):
    '''Backup the text file and then write the new content.

      Log any io errors and then raise another ioerrr.
    '''

    backup(filename)

    return write(filename, lines, append)


def backup(filename):
    '''Backup the text file.

      Log any io errors and then raise another ioerrr.
    '''

    try:
        shutil.copy2(filename, filename + '.bak')

    except IOError as io_error:
        (errno, strerror) = io_error.args
        log(f'Unable to backup {filename}')
        log(f"   ({errno:d}) {strerror}")
        raise IOError
