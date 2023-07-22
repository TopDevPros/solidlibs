'''
    Text formating.

    Because this module uses some modules that use this one,
    imports that are not from standard libs should not be
    at global scope. Put the import where it's used.

    Copyright 2008-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

from collections.abc import Iterable
try:
    import json_tricks as json
except ImportError:
    import json
import locale
import os
import pprint
import re
from traceback import format_exc

UNICODE_DECODINGS = ['utf-8',
                     'iso-8859-14',
                     locale.getpreferredencoding(False)]
DETAILED_LOG = '/tmp/solidlibs.python.format.detailed.log'

# delayed import of log so solidlibs.python.log can use this module
_log = None


def log(message):
    global _log
    if not _log:
        from solidlibs.python.log import Log
        _log = Log()
    _log(message)


# delayed open of detailed log so other users can use this module
_detailed_log = None


def detailed_log(message):
    global _detailed_log
    if not _detailed_log:
        _detailed_log = open(DETAILED_LOG, 'w')
        # user frequently changes, so loosen access
        os.chmod(DETAILED_LOG, 0o660)
    _detailed_log.write(message)
    _detailed_log.flush()

def pretty(obj, indent=4, base_indent=0):
    ''' Prettyprint 'pprint' replacement.

        Places every dictionary item on a separate line in key order.
        Formats nested dictionaries.

        For long lists, places every item on a separate line.

        'indent' is the increment for each indentation level, and defaults to 4.
        'base_indent' is the current indentation, and defaults to 0.

    >>> import datetime
        >>> data = {
        ...     'a': 1,
        ...     'c': 2,
        ...     'b': 'hi',
        ...     'x': {1: 'a', 2: 'b'},
        ...     'e': datetime.timedelta(days=9, seconds=11045),
        ...     'd': 'ho',
        ...     'g': datetime.datetime(2000, 1, 2, 3, 4, 5, 6),
        ...     'f': datetime.date(2000, 1, 2),
        ...     'h': datetime.time(1, 2, 3, 4),
        ...     }
        >>> data['l'] = [data['a'], data['b'], data['c'], data['d'], data['e'], data['f'], data['g'], data['h'], data['x']]
        >>> p = pretty(
        ...     data,
        ...     indent=4
        ...     )
        >>> print(p)
        {
            'a': 1,
            'b': 'hi',
            'c': 2,
            'd': 'ho',
            'e': datetime.timedelta(days=9, seconds=11045),
            'f': datetime.date(2000, 1, 2),
            'g': datetime.datetime(2000, 1, 2, 3, 4, 5, 6),
            'h': datetime.time(1, 2, 3, 4),
            'l': [
                1,
                'hi',
                2,
                'ho',
                datetime.timedelta(days=9, seconds=11045),
                datetime.date(2000, 1, 2),
                datetime.datetime(2000, 1, 2, 3, 4, 5, 6),
                datetime.time(1, 2, 3, 4),
                {
                    1: 'a',
                    2: 'b',
                },
            ],
            'x': {
                1: 'a',
                2: 'b',
            },
        }

        >>> p1 = eval(p)
        >>> print(pretty(p1, indent=4))
        {
            'a': 1,
            'b': 'hi',
            'c': 2,
            'd': 'ho',
            'e': datetime.timedelta(days=9, seconds=11045),
            'f': datetime.date(2000, 1, 2),
            'g': datetime.datetime(2000, 1, 2, 3, 4, 5, 6),
            'h': datetime.time(1, 2, 3, 4),
            'l': [
                1,
                'hi',
                2,
                'ho',
                datetime.timedelta(days=9, seconds=11045),
                datetime.date(2000, 1, 2),
                datetime.datetime(2000, 1, 2, 3, 4, 5, 6),
                datetime.time(1, 2, 3, 4),
                {
                    1: 'a',
                    2: 'b',
                },
            ],
            'x': {
                1: 'a',
                2: 'b',
            },
        }
    '''

    max_list_width = 60

    if isinstance(obj, dict):
        p = '{\n'
        base_indent += indent
        try:
            keys = sorted(obj.keys())
        except:    # pylint:bare-except -- catches more than "except Exception"
            keys = obj.keys()
        for key in keys:
            p += (' ' * base_indent) + repr(key) + ': '
            value = obj[key]
            p += pretty(value, indent=indent, base_indent=base_indent)
            p += ',\n'
        base_indent -= indent
        p += (' ' * base_indent) + '}'

    elif isinstance(obj, list):
        p = '[\n'
        base_indent += indent
        for item in obj:
            p += (' ' * base_indent) + pretty(item, indent=indent, base_indent=base_indent)
            p += ',\n'
        base_indent -= indent
        p += (' ' * base_indent) + ']'
        # put short lists on one line
        if len(p) < max_list_width:
            p = p.replace('\n ', ' ')
            p = p.replace('  ', ' ')

    else:
        pp = pprint.PrettyPrinter(indent=indent)
        try:
            p = pp.pformat(obj)
        except:    # pylint:bare-except -- catches more than "except Exception"
            try:
                log(f'unable to pretty print object: {obj}')
                p = repr(obj)
                log(f'object len: {len(p)}')
            except:    # pylint:bare-except -- catches more than "except Exception"
                log(format_exc())
                from solidlibs.python.utils import last_exception_only
                p = f'solidlibs.python.format.pretty ERROR:{last_exception_only()}'

    return p

def format_float(number, commas=True, decimal_places=2):
    ''' Format for commas and decimal places.

        Args:
            number:         A raw number (int or float).
            commas:         If True, add commas between thousands, etc.
                            Optional. Defaults to True.
            decimal_places: The digits you want kept to the right of the decimal places.
                            If fewer digits than specified, 0s added to fill the places
                            Optional. Defaults to 2.

        Returns:
            The number in string format with commas and decimal places as specified.

        >>> print(format_float(0))
        0.00
        >>> print(format_float(1))
        1.00
        >>> print(format_float(1234))
        1,234.00
        >>> print(format_float(1234567))
        1,234,567.00
        >>> print(format_float(0.0))
        0.00
        >>> print(format_float(0.1234))
        0.12
        >>> print(format_float(1.1234))
        1.12
        >>> print(format_float(1234.1234))
        1,234.12
        >>> print(format_float(1234567.1234, decimal_places=2))
        1,234,567.12
        >>> print(format_float(1234567.1, decimal_places=2))
        1,234,567.10
    '''

    if commas:
        comma = ','
    else:
        comma =''

    decimal_format = '{:' + comma + '.' + str(decimal_places) + 'f}'

    return decimal_format.format(number)

def s_if_plural(number):
    ''' Return an empty string if the number is one, else return the letter \'s\'.
        This is used to form standard plural nouns.

        >>> print('house' + s_if_plural(0))
        houses
        >>> print('house' + s_if_plural(1))
        house
        >>> print('house' + s_if_plural(2))
        houses

    '''

    if number == 1:
        result = ''
    else:
        result = 's'
    return result

def replace_angle_brackets(s):
    ''' Replace '<' with '&lt;' and '>' with '&gt;'.

        This allows html to display correctly when embedded in html. '''

    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    return s

def replace_ampersand(s):
    ''' Replace '&' with '&amp;'.

        This allows html to display correctly when embedded in html.

        >>> s = 'Terms & Conditions'
        >>> replace_ampersand(s)
        'Terms &amp; Conditions'
        >>> s = '&lt;'
        >>> replace_ampersand(s)
        '&lt;'
    '''

    s = s.replace(' & ', ' &amp; ')
    return s

def camel_back(s):
    ''' Combine words into a string with no spaces and every word capitalized.
        Already capitalized letters after the first letter are preserved.

        >>> camel_back('wikipedia article name')
        'WikipediaArticleName'
        >>> camel_back('WikiPedia CamelBack')
        'WikiPediaCamelBack'

        '''

    words = s.split(' ');
    camel_back_words = []
    for word in words:
        # the word may itself be camel back, or at least have some capitalized letters
        camel_back_words.append(word[:1].capitalize() + word[1:])
    return ''.join(camel_back_words)

def pretty_html(html, parser=None):
    ''' Prettyprint html.

        Requires BeautifulSoup, python3-tidylib, or python3-utidylib.

        'parser' specifies the parser used by BeautifulSoup. 'html5lib'
        is the most lenient and the default. 'lxml' is the fastest.

        >>> html = '<head><title>Test HTML</title></head><body>The test text</body>'
        >>> html_prettied = pretty_html(html)
        >>> assert isinstance(html_prettied, str)
        >>> '<html>' in html_prettied
        True
        >>> '</html>' in html_prettied
        True

        >>> bytes_html = b'<head><title>Test HTML</title></head><body>The test text</body>'
        >>> pretty_bytes_html = pretty_html(bytes_html)
        >>> assert isinstance(pretty_bytes_html, bytes)
        >>> b'<html>' in pretty_bytes_html
        True
        >>> b'</html>' in pretty_bytes_html
        True
    '''

    def append_line(line):
        line = line.strip()
        log(f'line: {line}') # DEBUG
        lines.append(line)

    #log(f'type(html): {type(html)}')
    #log(f'repr(html): {repr(html)}')
    WAS_STRING = isinstance(html, str)
    #log(f'WAS_STRING: {WAS_STRING}')
    if WAS_STRING:
        html = to_bytes(html)
        #log(f'type(html) after to_bytes: {type(html)}')

    if parser is None:
        parser = 'html5lib'
        #log('using html5lib parser')

    # try various html prettyprinters
    p_html = None

    try:
        from bs4 import BeautifulSoup, FeatureNotFound

        #log(f'clean html with beautifulsoup prettify, parser: {parser}')

        soup = BeautifulSoup(html, features=parser)
        p_html = soup.prettify(encoding='utf-8')

    except ImportError:
        pass

    except FeatureNotFound:
        pass

    except:    # pylint:bare-except -- catches more than "except Exception"
        log.exception_only()

    if not p_html:
        try:
            # python3-tidylib
            from tidylib import tidy_document

            if b'<frameset' in html:
                raise ValueError('tidy_document() does not work with framesets')

            p_html, errors = tidy_document(html)
            if errors:
                # rss is not html
                if '<rss> is not recognized' in errors:
                    log("Warning: tidy prettyprinter can't format rss")
                else:
                    pass
                    #log("Warning: tidy prettyprinter found errors")
                    # log(f"see {DETAILED_LOG}")
                    # detailed_log(f'tidy error: {errors}\n')
            elif not p_html:
                log('tidy returned an empty page')

        except ImportError:
            log('No module named tidylib. Install debian package python3-tidylib or pypi package pytidylib.')
        except:    # pylint:bare-except -- catches more than "except Exception"
            log.exception_only()

    if not p_html:
        try:
            # python3-utidylib
            import tidy

            options = dict(output_xhtml=1, add_xml_decl=1, indent=1, tidy_mark=0)
            try:
                p_html = str(tidy.parseString(html, **options))
            except AttributeError as aerr:
                # not debugged:
                #      module 'tidy' has no attribute 'parseString'
                # maybe need to install/reinstall python3-utidylib
                log.warning(str(aerr))

        except ImportError:
            log('No module named tidy')
        except:    # pylint:bare-except -- catches more than "except Exception"
            log.exception_only()

        else:
            if not p_html:
                log('empty string from python3-utidylib')

    if not p_html:
        # import late to avoid conflicts

        log.warning('unable to prettyprint html')
        p_html = html

        """
        # ad hoc prettyprinter, indents tag/endtag blocks

        log('solidlibs.python.format() NOT WORKING') # DEBUG
        log.stacktrace()) # the caller needs to handle a returned value of None

        # split into lines
        lines = []
        line = ''
        quote_char = None # or quote char
        for ch in html:

            #log(f'ch: {repr(ch)}') # DEBUG
            # if type(html) is bytes, then type(ch) is int
            if isinstance(ch, int):
                ch = chr(ch)
                #log(f'ch changed to: {repr(ch)}') # DEBUG

            if quote_char:
                #log('in quote') # DEBUG
                # don't look for tags in quoted strings
                line = line + ch
                if ch == quote_char:
                    quote_char = None

            elif ch in ('"', "'"):
                #log(f'start quote: {ch}') # DEBUG
                quote_char = ch
                line = line + ch

            # look for tags
            elif ch == '<':
                log('start tag, end of previous line') # DEBUG
                if line:
                    lines.append(line.strip())
                line = '<'
            elif ch == '>':
                log('end tag char') # DEBUG
                if line:
                    log('end tag char, so end of line') # DEBUG
                    line = line + ch
                    append_line(line)
                    line = ''
                else:
                    log('probably not a tag') # DEBUG
                    line = line + ch

            else:
                line = line + ch

        # finish last line, if any
        if line:
            append_line(line)
        #log('lines done')

        # indent blocks with endtags
        start_tag_pattern = re.compile(b'^<\s*([A-Za-z]+)\b.*>')
        end_tag_pattern = re.compile(b'^</\s*([A-Za-z]+)\b.*>')
        reversed_rough = []
        tags = []
        indent = 0
        for line in reversed(lines):

            end_match = end_tag_pattern.match(line)
            if end_match:
                endtag = end_match.group(1)
                tags.append(endtag)
                reversed_rough.append((indent * b'    ') + line)
                indent += 1

            else:
                start_match = start_tag_pattern.match(line)
                if start_match:
                    starttag = start_match.group(1)
                    if starttag in tags:
                        del tags[tags.index(starttag)]
                        if indent:
                            indent -= 1
                reversed_rough.append((indent * b'    ') + line)

        # remove excess indent
        first = reversed_rough[-1]
        excess_count = len(first) - len(first.lstrip())
        excess = b' ' * excess_count
        reversed_lines = []
        for line in reversed_rough:
            if line.startswith(excess):
                line = line[excess_count:]
            reversed_lines.append(line)

        # join lines
        lines = reversed(reversed_lines)
        p_html = b'\n'.join(lines)
        """

    assert p_html, 'Unable to prettyprint. Tried BeautifulSoup, python3-tidylib, python3-utidylib, and ad hoc'
    #log(f'p_html:\n{f}') # DEBUG

    #log(f'at end of p_html() WAS_STRING: {WAS_STRING}') # DEBUG
    if WAS_STRING:
        #log('at end of p_html() call to_string(html)') # DEBUG
        p_html = to_string(p_html)
    #log(f'at end of p_html() type(html): {type(html)}') # DEBUG

    return p_html

def pretty_json(json_string, indent=4):
    ''' Prettyprint json string.

        >>> json_string = '{"b": 2, "a": 1, "d": {"y": "b", "x": "a"}, "c": 3}'
        >>> print(pretty_json(json_string))
        {
            "a": 1,
            "b": 2,
            "c": 3,
            "d": {
                "x": "a",
                "y": "b"
            }
        }

    '''

    decoded = json.loads(json_string)
    encoded = json.dumps(decoded, indent=indent, sort_keys=True)
    return encoded

def to_json(data, indent=4):
    ''' Convert to json.

        If TypeError, log data.
    '''

    try:
        json_data = json.dumps(data, indent=indent)

    except TypeError as ve:
        pp = pprint.PrettyPrinter(indent=indent)

        p = pp.pformat(data)
        log(f'{ve}:\n{p}')

        raise

    else:
        return json_data

def pretty_called_process_error(cpe):
    ''' Pretty-print subprocess.CalledProcessError

        <<< cpe = {"args": \
                   {"stderr": "Traceback (most recent call last):                      File \"/var/local/projects/tools/renew_cert.py\", line 32, in <module>                      print(pretty_called_process_error(cpe))                      File \"/usr/local/lib/python3.9/dist-packages/solidlibs/python/format.py\", line 582, in pretty_called_process_error                      pretty = pretty + pretty_text("stdout", cpe.stdout)                      File "/usr/local/lib/python3.9/dist-packages/solidlibs/python/format.py", line 567, in pretty_text                      text = text.decode().strip()                      AttributeError: \'str\' object has no attribute \'decode\'", "stdout": "", "return_code": 1}\
                  }
        <<< pretty_called_process_error(cpe)
    '''

    def pretty_text(label, text):
        if text:
            if not isinstance(text, str):
                text = text.decode().strip()
            text.replace('\n', '\n\t\t')
            text = '\t' + label + ':\n\t\t' + text

        else:
            text = ''

        return text

    pretty = 'subprocess.CalledProcessError\n'

    command_args = list(map(str, cpe.args))
    command_str = ' '.join(command_args)
    pretty = pretty + '\t' + command_str + '\n'
    pretty = pretty + '\t' + f'error returncode: {cpe.returncode}' + '\n'
    pretty = pretty + pretty_text('stdout', cpe.stdout)
    pretty = pretty + pretty_text('stderr', cpe.stderr)

    return pretty

def read_unicode(stream, errors=None):
    ''' Try to decode a stream of bytes to a unicode string.
        Replacement for stream.read().

        There has got to be a standard way to do this that works, but haven't found it.

        If not decoded raises UnicodeDecodeError.

        If stream is not bytes raises TypeError.

        To do:
            Use encoding hints, e.g. http's Content-Encoding::
                content-type = text/html; charset=UTF-8
                or from python::
                    charset = solidlibs.net.http_addons.content_encoding_charset(params)
                or html's content-type::
                    <meta http-equiv="content-type" content="text/html; charset=UTF-8">
    '''

    if errors is None:
        errors = 'strict'

    decodings = UNICODE_DECODINGS
    decoded = None

    data = stream.read()

    if isinstance(data, str):
        decoded = data

    else:
        for encoding in decodings:
            if decoded is None:
                try:
                    decoded = str(data, encoding, errors)

                except UnicodeDecodeError:
                    pass

    if decoded is None:
        raise UnicodeDecodeError(f'unable to decode unicode using {repr(UNICODE_DECODINGS)}')

    return decoded

def less_whitespace(s):
    ''' Remove repeated blank lines, and white space at the end of lines.

        >>> # see https://stackoverflow.com/questions/40918168/docstring-has-inconsistent-leading-whitespace
        >>> s = 'a    \\nb\\n\\n\\n\\nc'
        >>> print(less_whitespace(s))
        a
        b
        c
    '''

    s = re.sub(r'[ \t]+\n', '\n', s, flags=re.MULTILINE)
    s = re.sub(r'\n+', '\n', s, flags=re.MULTILINE)

    return s

def strip_html(html):
    '''
        Remove all the html and return only plain text.

        >>> html = '<html>\\n<head>\\n<title>Test HTML</title>\\n</head>\\n<body>The test text</body>\\n</html>'
        >>> strip_html(html).strip()
        'Test HTML \\n \\n The test text'
        >>> html = '{# Copyright 2023 solidlibs #}\\n<body>Another test</body>\\n</html>'
        >>> strip_html(html).strip()
        'Another test'
        >>> html = '<body>Yet another test</body>\\n{% block %}\\n something\\n {% endblock %}</html>'
        >>> strip_html(html).strip()
        'Yet another test \\n{% block %}\\n something'
        >>> html = '{% comment %}\\n Copyright 2023 solidlibs\\n{% endcomment %}\\n<body>Last test</body>\\n</html>'
        >>> strip_html(html).strip()
        'Last test'
    '''
    def get_start_and_end(line):
        start_index = line.find('<')
        if start_index == -1:
            start_index = line.find('{#')
            if start_index == -1:
                start_index = line.find('{{')
                end = '}}'
            else:
                end = '#}'
        else:
            end = '>'

        return start_index, end

    new_lines = []
    skip_line = False

    lines = html.split('\n')
    for line in lines:
        done = False
        while not done:
            if line.find('{% comment %}') >= 0:
                new_lines.append(' \n')
                skip_line = True
                done = True
            elif skip_line:
                new_lines.append(' \n')
                if line.find('{% endcomment %}') >= 0:
                    skip_line = False
                done = True
            elif line.find('{% endblock') >= 0:
                new_lines.append(' \n')
                done = True
            else:
                start_index, end = get_start_and_end(line)
                if start_index >= 0:
                    end_index = line.find(end)
                    if end == '#}' or end == '}}':
                        end_index += 1
                    if end_index > start_index:
                        html_text = line[start_index:end_index+1]
                        line = line.replace(html_text, ' ')
                    else:
                        new_lines.append(line[:start_index] + ' ')
                        line = line[start_index + 1:]
                else:
                    done = True
                    new_lines.append(line)

    return '\n'.join(new_lines)

def to_bytes(obj):
    ''' Convert string to bytes.

        'obj' must be a string or bytes. If obj is bytes or bytearray, it is unchanged.

        Convenience function because no one can remember what .encode()
        and .decode() do.

        Replacement for string.encode().
    '''

    if isinstance(obj, (bytearray, bytes)):
        encoded = obj

    else:
        if repr(obj).startswith("b'"): raise Exception(f'apparent byte literal as string: {obj}') # DEBUG
        encoded = None
        for encoding in UNICODE_DECODINGS:
            if encoded is None:
                try:
                    encoded = obj.encode(encoding)
                    if isinstance(encoded, str):
                        log(f'unable to encode string. type after encoding is {type(encoded)}')
                        encoded = None

                except UnicodeEncodeError:
                    pass

        if encoded is None:
            raise UnicodeEncodeError(f'unable to encode unicode using {repr(UNICODE_DECODINGS)}')

        assert isinstance(encoded, bytes)

    return encoded

def to_string(obj):
    ''' Convert bytes to string.

        'obj' must be a string or bytes. If obj is a string, it is unchanged.

        If not decoded raises UnicodeDecodeError.

        Replacement for bytes.decode().
    '''

    if isinstance(obj, str):
        decoded = obj

    else:
        decoded = None
        for encoding in UNICODE_DECODINGS:
            if decoded is None:
                try:
                    decoded = obj.decode(encoding)

                except UnicodeDecodeError:
                    pass

        if decoded is None:
            raise UnicodeDecodeError(f'unable to decode unicode using {repr(UNICODE_DECODINGS)}')

        assert isinstance(decoded, str)

    return decoded

def encode_unicode(string):
    ''' Deprecated Use to_string(). '''

    raise DeprecationWarning('Use to_bytes() instead of encode_unicode()')

    return to_bytes(string)

def decode_unicode(string):
    ''' Deprecated. Use to_string(). '''

    raise DeprecationWarning('Use to_string() instead of decode_unicode()')

    return to_string(string)

def add_commas(number, decimal_places=0):
    ''' Deprecated. Use format_float().
    '''

    raise DeprecationWarning('Use format_float() instead of add_commas()')

    return format_float(number, decimal_places=decimal_places)


def is_json_value_error(data, datapath=None):
    ''' NOT WORKING

        Analyze data for errors such as

            "ValueError: Out of range float values", i.e. inf

        Needs work.
    '''

    # while the current data is bad, recurse
    try:
        to_json(data)

    except (ValueError, TypeError):
        if datapath is None:
            datapath = ''

        if isinstance(data, dict):
            found_error = False
            for key in data:
                if not found_error:
                    newpath = is_json_value_error(data[key], datapath)
                    if newpath is not None:
                        found_error = True
                        datapath = newpath + '[' + repr(key) + ']'

        else:
            try:
                found_error = False
                for item in iter(data):
                    if not found_error:
                        newpath = is_json_value_error(item, datapath)
                        if newpath is not None:
                            found_error = True
                            datapath = newpath + '[' + repr(key) + ']'

            except TypeError as t_err:
                # not iterable
                # log(f'{t_err}: datapath: {datapath}')
                pass

            else:
                # not dict or iterable
                datapath = datapath + repr(data)

    else:
        # this datapath is ok, so don't return it
        datapath = None

    return datapath


if __name__ == "__main__":
    import doctest
    doctest.testmod()
