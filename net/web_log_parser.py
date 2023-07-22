'''
    Parse an apache compatible access log line.

    Copyright 2012-2023 solidlibs
    Last modified: 2023-05-17
'''

import re
from datetime import datetime, timezone

from solidlibs.net.browser import get_agent_info
from solidlibs.python.dict import Simple
from solidlibs.python.utils import is_string

try:
    from solidlibs.python.log import Log
    log = Log()
except:   # NOQA
    def log(message):
        print(message)
debug = True
def note(*args):
    print(args)
    log(*args)


class LogLine(Simple):
    """
    Parse a web log line.

    >>> access = LogLine(b'200.217.153.246 - - [10/Dec/2019:03:36:17 +0000] "GET /trader/trial/ HTTP/1.0" 200 85755 "https://example.com/" "Mozilla/5.0 (Wayland; Linux x86_64; rv:58.0) Gecko/20100101 Firefox/58.0"')

    >>> access.ip_address
    '200.217.153.246'
    >>> access.domain
    ''
    >>> access.user
    ''
    >>> access.timestamp
    datetime.datetime(2019, 12, 10, 3, 36, 17, tzinfo=datetime.timezone.utc)
    >>> access.method
    'GET'
    >>> access.url
    '/trader/trial/'
    >>> access.query_string
    ''
    >>> access.protocol
    'HTTP/1.0'
    >>> access.http_status_code
    200
    >>> access.bytes
    85755
    >>> access.referer
    'https://toparb.com/'
    >>> access.agent
    'Mozilla/5.0 (Wayland; Linux x86_64; rv:58.0) Gecko/20100101 Firefox/58.0'


    >>> access = LogLine(b'172.105.23.36 - - [10/Dec/2019:06:01:22 +0000] "GET / HTTP/1.1" 400 173 "-" "-"')
    >>> access.ip_address
    '172.105.23.36'
    >>> access.domain
    ''
    >>> access.user
    ''
    >>> access.timestamp
    datetime.datetime(2019, 12, 10, 6, 1, 22, tzinfo=datetime.timezone.utc)
    >>> access.method
    'GET'
    >>> access.url
    '/'
    >>> access.query_string
    ''
    >>> access.protocol
    'HTTP/1.1'
    >>> access.http_status_code
    400
    >>> access.bytes
    173
    >>> access.referer
    ''
    >>> access.agent
    ''

    >>> access = LogLine(b'184.156.108.45 - - [10/Dec/2019:19:25:50 +0000] "GET /rescue/downloads/example-rescue_0.9-1_all.deb HTTP/1.1" 200 7186896 "https://toparb.com/rescue/downloads/" "Mozilla/5.0 (Windows NT 6.3; WOW64; rv:39.0) Gecko/20100101 Firefox/39.0"')
    >>> access.ip_address
    '184.156.108.45'
    >>> access.domain
    ''
    >>> access.user
    ''
    >>> access.timestamp
    datetime.datetime(2019, 12, 10, 19, 25, 50, tzinfo=datetime.timezone.utc)
    >>> access.method
    'GET'
    >>> access.url
    '/rescue/downloads/example-rescue_0.9-1_all.deb'
    >>> access.query_string
    ''
    >>> access.protocol
    'HTTP/1.1'
    >>> access.http_status_code
    200
    >>> access.bytes
    7186896
    >>> access.referer
    'https://toparb.com/rescue/downloads/'
    >>> access.agent
    'Mozilla/5.0 (Windows NT 6.3; WOW64; rv:39.0) Gecko/20100101 Firefox/39.0'

    >>> line = b'216.244.66.196 - - [10/Dec/2019:06:21:47 +0000] "GET /trader/opportunities/ HTTP/1.1" 200 86165 "-" "BusinessBot: Nathan@lead-caddy.com"'
    >>> access = LogLine(line)
    >>> access.agent
    'BusinessBot: Nathan@lead-caddy.com'
    >>> access.browser_name
    ''
    >>> access.other
    'BusinessBot: Nathan@lead-caddy.com'

    IMPORTANT: Be careful not to start or end any lines with triple quotes,
    unless the quoted string is a comment.
    Our code that strips code comments for distribution may break.
    For example, the following regular expression *won't work* unless the
    r''' is moved to the next line, afterleading spaces and ''', line can't start the line:

    Bad:
        Line_Format = re.compile(r'''
                                 (?P<ip_address>.*?),?\s"
                                 ''',
                                 re.VERBOSE)
    Good (at least it works with the comment stripping code):
        Line_Format = re.compile(
                                 r'''
                                 (?P<ip_address>.*?),?\s" ''',
                                 re.VERBOSE)
    """

    Line_Format = re.compile(
        r'''(?P<ip_address>.*?),?\s

        (
            (-) # missing domain
            |
            (
                (?P<domain>.+?)
            )
        )\s

        (
            (-) # missing user
            |
            (
                (?P<user>.+?)
            )
        )\s

        \[
            (?P<timestamp>.*?)
        \]\s

        "
            (
                (-) # missing method/url/protocol
                |
                (
                    (?P<method>.+?)\s
                    (?P<url>.+?)
                    (\?(?P<query_string>.+?))?\s
                    (?P<protocol>.+?)
                )
            )
        "
        \s

        (?P<http_status_code>\d+)\s
        (?P<bytes>.+?)\s

        "
            (
                (-) # missing referer
                |
                (
                    (?P<referer>.+?)
                )
            )
        "\s

        "
            (
                (-) # missing agent
                |
                (
                    (?P<agent>.+?)
                )
            )
        " ''',
        re.VERBOSE)
    # old: Line_Format = re.compile(r'''(?P<ip_address>.*?),? (?P<domain>.*?) (?P<user>.*?) \[(?P<timestamp>.*?)\] "(?P<method>.*?) (?P<url>.*?)(\?(?P<query_string>.*?))? (?P<protocol>.*?)" (?P<http_status_code>\d*) (?P<bytes>.*?) "(?P<referer>.*?)" "(?P<agent>.*?)"''')
    # testing 2: Line_Format = re.compile(r'''(?P<ip_address>.*?),? (?P<domain>.*?) (?P<user>.*?) \[(?P<timestamp>.*?)\] "((?P<method>.*?) (?P<url>.*?)(\?(?P<query_string>.*?))? (?P<protocol>.*?))?" (?P<http_status_code>\d*) (?P<bytes>.*?) "(?P<referer>.*?)" "(?P<agent>.*?)"''')

    Date_Format = re.compile(r'''(?P<day>\d*)/(?P<month>.*)/(?P<year>\d*):(?P<hour>\d*):(?P<min>\d*):(?P<sec>\d*) *(?P<gmt_offset>.*)''')
    Page_Not_Found_Format = re.compile(r'''(?P<ip_address>.*?),? (?P<domain>.*?) (?P<user>.*?) \[(?P<timestamp>.*?)\] ".*?" 400 \d{1,3} "-" "-"''')
    #Ip_Address_Format = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")

    NOT_APACHE_FORMAT = 'Not in apache log format'

    def __init__(self, line):
        ''' Line is a line from an apache compatible web log. '''

        self.line = line

        m = LogLine.Line_Format.search(str(line))
        if m:
            self.ip_address = LogLine.get_string(m.group('ip_address'))
            if not is_string(self.ip_address):
                self.ip_address = self.ip_address.decode()
            self.domain = LogLine.get_string(m.group('domain'))
            self.method = LogLine.get_string(m.group('method'))
            if self.method:
                self.method = self.method.upper()

            self.timestamp = LogLine.get_timestamp(m.group('timestamp'))

            self.referer = LogLine.get_string(m.group('referer'))
            if self.referer and self.referer == '-':
                self.referer = ''

            self.url = LogLine.get_string(m.group('url'))
            self.query_string = LogLine.get_string(m.group('query_string'))
            self.http_status_code = LogLine.get_int(m.group('http_status_code'))
            self.protocol = LogLine.get_string(m.group('protocol'))
            self.bytes = LogLine.get_int(m.group('bytes'))

            self.user = LogLine.get_string(m.group('user'))
            if self.user and self.user == '-':
                self.user = ''

            self.agent = LogLine.get_string(m.group('agent'))
            self.browser_name, self.browser_version, self.other = LogLine.get_browser_info(self.agent)

        else:
            message = f'{LogLine.NOT_APACHE_FORMAT}: {line}'

            if not is_string(line):
                line = line.decode()
            m = LogLine.Page_Not_Found_Format.search(line)
            if not m:
                log(message)
            # but still raise the error so we don't process the entry
            raise ValueError(message)

    @staticmethod
    def get_string(item):
        '''Get a stripped string from the item.

           If the item is None, then return an empty string.
       '''

        string = item
        if item is None:
            string = ''
        else:
            # some strings have what looks like embedded byte code
            string = string.strip().lstrip("b'")

        return string

    @staticmethod
    def get_int(item):
        if item:
            try:
                the_bytes = int(item)
            except NameError or ValueError:
                the_bytes = None
        else:
            the_bytes = None

        return the_bytes

    @staticmethod
    def get_timestamp(item):
        '''Parse the date/time from the string.'''

        # import delayed to avoid recusive import
        import solidlibs.python.times    # pylint: disable=import-outside-toplevel

        if item:

            m = LogLine.Date_Format.search(item)
            if m:
                hour = int(m.group('hour'))
                minutes = int(m.group('min'))
                seconds = int(m.group('sec'))
                day = int(m.group('day'))
                month = solidlibs.python.times.MONTH_MAP[m.group('month')]
                year = int(m.group('year'))

                date_time = datetime(year, month, day, hour, minutes, seconds, tzinfo=timezone.utc)

            else:
                date_time = None

        else:
            date_time = None

        return date_time

    @staticmethod
    def get_browser_info(item):
        '''Parse the browser info from the string.

            >>> LogLine.get_browser_info('Mozilla/5.0 (compatible; Yahoo! Slurp/3.0; http://help.yahoo.com/help/us/ysearch/slurp)')
            ('Mozilla', '5.0', '(compatible; Yahoo! Slurp/3.0; http://help.yahoo.com/help/us/ysearch/slurp)')
            >>> LogLine.get_browser_info('BusinessBot: Nathan@lead-caddy.com')
            ('', '', 'BusinessBot: Nathan@lead-caddy.com')
        '''

        browser_name, browser_version, other = get_agent_info(item)

        return (browser_name, browser_version, other)

    @staticmethod
    def full_url(access):
        ''' Return the full url with query string.'''

        url = access.url
        if access.query_string:
            url += f'?{access.query_string}'

        return url


if __name__ == "__main__":

    import doctest
    doctest.testmod()
