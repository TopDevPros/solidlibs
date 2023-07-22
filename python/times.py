'''
    Times.

    Utilties for times. Great for working with time series.

    Todo: Handle timezones better. See parse_timestamp(timezone=...),

    Copyright 2009-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import calendar
from contextlib import contextmanager
import re
import time
import human_readable
# avoid conflict with 'timezone' param
from datetime import timezone as datetime_timezone
from datetime import date, datetime, timedelta

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    ZONE_INFO_AVAILABLE = True
    PYTZ_AVAILABLE = False
except ImportError:
    ZONE_INFO_AVAILABLE = False
    try:
        import pytz
        from pytz.exceptions import UnknownTimeZoneError
    except ImportError:
        PYTZ_AVAILABLE = False
    else:
        PYTZ_AVAILABLE = True


from solidlibs.net.web_log_parser import LogLine
from solidlibs.python.format import s_if_plural
from solidlibs.python.log import Log
from solidlibs.python.utils import format_exception

# map month abbrevs to numeric equivalent
MONTH_MAP = {'Jan': 1,
             'Feb': 2,
             'Mar': 3,
             'Apr': 4,
             'May': 5,
             'Jun': 6,
             'Jul': 7,
             'Aug': 8,
             'Sep': 9,
             'Oct': 10,
             'Nov': 11,
             'Dec': 12}

# ISO 8901 datetime format with microseconds and timezone
ISO_DATETIME_RE = r'(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)[ T](?P<hour>\d+):(?P<minute>\d+):(?P<second>\d+)\.(?P<microsecond>\d*)(?P<timezone>.*)'
TIMEZONE_RE = re.compile(r'(?P<name>[a-zA-Z]{3})? *?((?P<sign>[+|-])(?P<hour>\d\d):(?P<minute>\d\d))?')

seconds_in_minute = 60
seconds_in_hour = 60 * seconds_in_minute
seconds_in_day = 24 * seconds_in_hour
microseconds_in_second = 1000000

# we don't define one_month, one_year, etc.
# because the exact definition varies from app to app
one_year = timedelta(days=365) # ignores leap year
one_week = timedelta(days=7)
one_day = timedelta(days=1)
one_hour = timedelta(hours=1)
one_minute = timedelta(minutes=1)
one_second = timedelta(seconds=1)
one_millisecond = timedelta(milliseconds=1)
one_microsecond = timedelta(microseconds=1)
no_time = timedelta(0)

far_past = datetime.min
far_future = datetime.max
# indicate all dates and times
anytime = far_future - one_microsecond

log = Log()
_compiled_timestamps = []

# some constants are defined after we define functions they need

class DatePeriod():
    '''
        Get a time series of consecutive dates between the start and end.

        >>> dp = DatePeriod('2000-01-01', '2000-01-02')
        >>> str(dp)
        'from 2000-01-01 to 2000-01-02'
        >>> date(2000, 1, 1) in dp
        True
        >>> date(3000, 1, 1) in dp
        False

        >>> dp = DatePeriod('2000-01-01')
        >>> str(dp)
        '2000-01-01'
        >>> date(2000, 1, 1) in dp
        True
        >>> date(3000, 1, 1) in dp
        False
    '''

    def __init__(self, start, end=None):
        ''' Return time period as (start, end).

            Args:
                start: Start of the period as a string or datetime.date.
                end:   End of the period as string or datetime.date.
                       If end is None, end is the same as start, and
                       the period is one day.
                       Optional. Defaults to None.

            Returns:
                A time series of consecutive dates from the start to the end, inclusive.
        '''

        self.start = self.type_check('start', start)
        if end:
            self.end = self.type_check('end', end)
        else:
            self.end = self.start

    def type_check(self, name, value):
        ''' Verify the value is a string or date.

            Args:
                name:  The name of the value (i.e., start or end).
                value: The value.

            Returns:
                The value if successfully verified.

            Raises:
                ValueError if the value is not a string or a date.
        '''
        if not isinstance(value, date):
            if isinstance(value, str):
                value = parse_timestamp(value).date()
            else:
                raise ValueError(f"'{name}' must be a date string or datetime.date")

        return value

    def __str__(self):
        if self.start == self.end:
            s = str(self.start)
        else:
            s = f'from {self.start} to {self.end}'

        return s

    def __contains__(self, date):
        date = self.type_check('date', date)
        return date >= self.start and date <= self.end

def now(utc=True):
    ''' Get the current datetime.

        Args:
            utc:  Whether to return date/time with or without timezone.
                  Optional. Defaults to True.

        Returns:
            If utc=True, return UTC date/time with timezone.
            If utc=False, return UTC date/time without timezone.

        >>> dt = now()
        >>> repr(dt.tzinfo)
        'datetime.timezone.utc'
    '''

    if utc:
        tzinfo = datetime_timezone.utc
    else:
        tzinfo = None

    if utc:
        dt = datetime.utcnow().replace(tzinfo=tzinfo)
    else:
        dt = datetime.now()
    return dt

def get_short_now(utc=True):
    '''
        Get datetime up to the minute, not the second or millisecond.

        Args:
            utc:  Whether to return date/time with or without timezone.
                  Optional. Defaults to True.

        Returns:
            The datetime up to the minute, not the second or millisecond.
            If utc=True, then timezone is included.
            If utc=False, then the timezone is not included.

        >>> get_short_now().second == 0 and get_short_now().microsecond == 0
        True
        >>> get_short_now(utc=True).second == 0 and get_short_now(utc=True).microsecond == 0
        True
    '''

    if utc:
        tzinfo = datetime_timezone.utc
    else:
        tzinfo = None

    time_now = now(utc=utc)
    return datetime(time_now.year, time_now.month, time_now.day,
                    time_now.hour, time_now.minute,
                    tzinfo=tzinfo)

def timestamp(when=None, microseconds=True):
    ''' Return timestamp as a string in a standard format. Time zone is UTC.

        Args:
            when:         A datetime or timestamp string.
                          Optional. Defaults to now.
            microseconds: True microseconds are included.
                          Optional. Defaults to True.

        Returns:
            The timestamp as a string in a standard format. Time zone is UTC.
            If microseconds=True, then microseconds are included.
            If microseconds=False, then microseconds are not included.

        Raises:
            ValueError: if when is not an instances of a str or a datetime.

        >>> re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d*?\+00:00$', timestamp()) is not None
        True
        >>> re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', timestamp(microseconds=False)) is not None
        True
    '''

    if when:
        if isinstance(when, str):
            when = parse_timestamp(when)
        elif not isinstance(when, datetime):
            raise ValueError("'when' must be a datetime, date/time string, or None")
    else:
        when = now()

    # datetime.str() returns ISO format
    formatted_time = when.isoformat(sep=' ')

    if not microseconds:
        i = formatted_time.rfind('.')
        if i > 0:
            formatted_time = formatted_time[:i]

    #log(f'formatted_time: {formatted_time}')

    return formatted_time

def parse_timestamp(timestr, startswith=False, default_year=None, timezone=None):
    ''' Parse a string timestamp. Return datetime.

        Args:
            timestr:      A time stamp in string format. Handles multiple formats
                          (see doctests below to see the variety of formats).
                          If timestr does not have a timezone and the 'timezone'
                          arg is not specified, the returned datetime is "naive",
                          meaning it does not have a timezone. It's recommended to
                          always specify the 'timezone' arg.
            startswith:   If True, only match a timestamp at the beginning of
                          the 'timestr' arg. If False, match a timestamp anywhere
                          in the 'timestr' arg.
                          Optional. Defaults to False
            default_year: Year to use in date, if one isn't specified in the 'timestr' arg.
                          Optional. Defaults to the current year. If process is
                          running when a new year starts, Windows defaults to zero.
            timezone:     a timezone string (e.g., 'UTC', 'EST').
                          If django reports a "TypeError: can't compare offset-naive
                          and offset-aware datetimes", then be sure to specify the
                          timezone to UTC or another appropriate timezone.
                          Optional. Defaults to None

        Returns:
            Return first timestamp found as an instance of datetime.

        Raises:
            ValueError: if no valid timestamp found.

        >>> # RFC 2616 required formats
        >>> #     RFC 822, updated by RFC 1123
        >>> ts = parse_timestamp('Sun, 06 Nov 1994 08:49:37 GMT')
        >>> ts.year
        1994
        >>> #     RFC 850, obsoleted by RFC 1036
        >>> ts = parse_timestamp('Sunday, 06-Nov-94 08:49:37 GMT')
        >>> ts.year
        94
        >>> #     ANSI C's asctime() format
        >>> ts = parse_timestamp('Sun Nov  6 08:49:37 1994')
        >>> ts.year
        1994
        >>> ts = parse_timestamp('Mon, 27 Apr 2020 15:55:56 GMT')
        >>> ts.day
        27

        >>> # no year
        >>> ts = parse_timestamp('Oct 28 11:06:55.000')
        >>> ts.year > 0
        True
        >>> ts.month
        10
        >>> ts.day
        28
        >>> ts.hour
        11
        >>> ts.minute
        6
        >>> ts.second
        55
        >>> ts.microsecond
        0

        >>> # no microseconds
        >>> parse_timestamp('Tue Jan 15 14:49:13 2000')
        datetime.datetime(2000, 1, 15, 14, 49, 13)

        >>> # no year and no microseconds
        >>> ts = parse_timestamp('Oct 28 11:06:55')
        >>> ts.year > 0
        True
        >>> ts.month
        10
        >>> ts.day
        28
        >>> ts.hour
        11
        >>> ts.minute
        6
        >>> ts.second
        55
        >>> ts.microsecond
        0

        # no year, single digit day, no microseconds
        >>> ts = parse_timestamp('Apr  9 18:17:01')
        >>> ts.year > 0
        True
        >>> ts.month
        4
        >>> ts.day
        9
        >>> ts.hour
        18
        >>> ts.minute
        17
        >>> ts.second
        1
        >>> ts.microsecond
        0

        >>> repr(parse_timestamp('1970-01-18T20:03:11.282Z'))
        'datetime.datetime(1970, 1, 18, 20, 3, 11, 282, tzinfo=datetime.timezone.utc)'

        >>> repr(parse_timestamp('2019-10-17 19:46:30.574Z'))
        'datetime.datetime(2019, 10, 17, 19, 46, 30, 574, tzinfo=datetime.timezone.utc)'

        >>> repr(parse_timestamp('17/Oct/2019:09:35:52 +0000'))
        'datetime.datetime(2019, 10, 17, 9, 35, 52, tzinfo=datetime.timezone.utc)'

        >>> repr(parse_timestamp('2021-04-20 08:31:58.773779+00:00'))
        'datetime.datetime(2021, 4, 20, 8, 31, 58, 773779, tzinfo=datetime.timezone.utc)'

        We're not handling this date string because
        different parts of the world interrupt this date differently.
        repr(parse_timestamp('02:07:36 05/08/03 EDT'))
        'datetime.datetime(5, 8, 3, 2, 7, 36)'

        >>> repr(parse_timestamp('2019-10-26 11:38:05.000711', timezone='UTC'))
        'datetime.datetime(2019, 10, 26, 11, 38, 5, 711, tzinfo=datetime.timezone.utc)'

        >>> repr(parse_timestamp('2019/10/17 12:40:36'))
        'datetime.datetime(2019, 10, 17, 12, 40, 36)'

        >>> repr(parse_timestamp('2019-10-23T17:55:00'))
        'datetime.datetime(2019, 10, 23, 17, 55)'

        >>> repr(parse_timestamp('02-11-2020 10:20:01'))
        'datetime.datetime(2020, 11, 2, 10, 20, 1)'

        >>> repr(parse_timestamp('2019-10-23T17:55:00UTC-07:30'))
        'datetime.datetime(2019, 10, 23, 17, 55, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=59400)))'

        >>> repr(parse_timestamp('2019-04-11T12:49:00 UTC+03:00'))
        'datetime.datetime(2019, 4, 11, 12, 49, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))'

        >>> repr(parse_timestamp('Oct 28 09:54:48'))
        'datetime.datetime(2022, 10, 28, 9, 54, 48)'

        >>> repr(parse_timestamp(b'Oct 28 09:54:48'))
        'datetime.datetime(2022, 10, 28, 9, 54, 48)'

        >>> repr(parse_timestamp(b'2021-10-28'))
        'datetime.datetime(2021, 10, 28, 0, 0)'

        >>> repr(parse_timestamp(date(2021, 10, 28)))
        'datetime.datetime(2021, 10, 28, 0, 0)'

        >>> repr(parse_timestamp(datetime(2021, 10, 28)))
        'datetime.datetime(2021, 10, 28, 0, 0)'

        >>> repr(parse_timestamp('2021-07-20 02:02:47.715.json', startswith=True))
        'datetime.datetime(2021, 7, 20, 2, 2, 47, 715)'

        >>> repr(parse_timestamp('2021-07-11 07:18:23.585+00:00.ticker.json', startswith=True))
        'datetime.datetime(2021, 7, 11, 7, 18, 23, 585, tzinfo=datetime.timezone.utc)'

        >>> repr(parse_timestamp('2021-02-09T08:30:11.613Z', startswith=True))
        'datetime.datetime(2021, 2, 9, 8, 30, 11, 613, tzinfo=datetime.timezone.utc)'

        >>> repr(parse_timestamp('2021-08-10 03:04:22.000092+00:00'))
        'datetime.datetime(2021, 8, 10, 3, 4, 22, 92, tzinfo=datetime.timezone.utc)'

        >>> if ZONE_INFO_AVAILABLE:
        ...     log.debug('test zoneinfo')
        ...     tz = ZoneInfo('UTC')
        ...     tz.key
        ... elif PYTZ_AVAILABLE:
        ...     log.debug('test pytz')
        ...     tz = pytz.timezone('UTC')
        ...     tz.zone
        'UTC'

        >>> if ZONE_INFO_AVAILABLE:
        ...     log.debug('test zoneinfo')
        ...     tz = ZoneInfo('EST')
        ...     tz.key
        ... elif PYTZ_AVAILABLE:
        ...     log.debug('test pytz')
        ...     tz = pytz.timezone('EST')
        ...     tz.zone
        'EST'

        >>> if ZONE_INFO_AVAILABLE:
        ...     try:
        ...        # zoneinfo can't handle Daylight Savings
        ...         ZoneInfo('EDT')
        ...     except ZoneInfoNotFoundError:
        ...        pass
        ... elif PYTZ_AVAILABLE:
        ...     print('pytz available')
        ...     # pytz can't handle Daylight Savings
        ...     try:
        ...         pytz.timezone('EDT')
        ...     except pytz.exceptions.UnknownTimeZoneError:
        ...         pass

        >>> if ZONE_INFO_AVAILABLE:
        ...     tz = ZoneInfo('Europe/Amsterdam')
        ...     tz.key
        ... elif PYTZ_AVAILABLE:
        ...     # pytz can't handle Daylight Savings
        ...     try:
        ...         pytz.timezone('EDT')
        ...     except pytz.exceptions.UnknownTimeZoneError:
        ...         pass
        'Europe/Amsterdam'

        >>> try:
        ...     repr(parse_timestamp('test'))
        ... except ValueError:
        ...     pass

    '''

    def parse_timezone(timezone_str):
        ''' Parse the timezone as an offset from UTC.

            Returns tzinfo or None.
        '''

        #log.debug(f'timezone_str: {timezone_str}')
        tzinfo = None

        if timezone_str == '+00:00':
            tzinfo = datetime_timezone.utc
        else:
            if ZONE_INFO_AVAILABLE:
                try:
                    tzinfo = ZoneInfo(timezone_str)
                except ZoneInfoNotFoundError:
                    #log.debug(f'timezone unknown to zoneinfo: {timezone_str}')
                    pass

            elif PYTZ_AVAILABLE:
                try:
                    tzinfo = pytz.timezone(timezone_str)
                except UnknownTimeZoneError:
                    #log.debug(f'timezone unknown to pytz: {timezone_str}')
                    pass

        if not tzinfo:
            match = TIMEZONE_RE.search(timezone_str)
            if match:
                mdict = match.groupdict()
                #log.debug(f'timezone dict: {mdict}')

                # name must be UTC; if it's not and zoneinfo wasn't able to
                # handle the conversion, then we'll ignore the timezone
                if 'name' in mdict:
                    if mdict['name']:
                        timezone_is_utc = mdict['name'].upper() == 'UTC'
                    else:
                        timezone_is_utc = True
                else:
                    timezone_is_utc = True

                if timezone_is_utc:
                    # timedelta() requires hour/minute
                    if ('sign' in mdict) and ('hour' in mdict) and ('minute' in mdict):

                        tz_sign = mdict['sign']
                        tz_hours = int(mdict['hour'])
                        tz_minutes = int(mdict['minute'])

                        offset = timedelta(hours=tz_hours, minutes=tz_minutes)
                        if tz_sign == '-':
                            offset = -offset
                        tzinfo = datetime_timezone(offset)
            else:
                log.debug(f'no timezone parsed. TIMEZONE_RE did not match. timestr: {timestr}')

        return tzinfo

    def get_timestamp(mdict, timezone):
        """ Timestamp regular expressions

            Match keywords must be the names of datetime.datetime parameters.

            The order of patterns is important. The patterns are tried in order.
            The first one to match is accepted. That means you need to
            list more complete ones first. For example, you should specify
            the tor log format before the syslog format. They are the same
            except the tor log format includes microseconds. So you want to
            match on microseconds if they are available, but still match
            on a different pattern when microseconds aren't available.

            Web log format is a special case handled in the code.
        """

        DATETIME_KEYWORDS = ['year', 'month', 'day',
                             'hour', 'minute', 'second', 'microsecond',
                             'tzinfo']

        #log.debug(f'mdict {mdict}') # DEBUG

        kwargs = {}
        for key in mdict:
            if key == 'timezone':
                value = mdict[key]
                kwargs[key] = value.strip()

            elif key == 'month':
                month = mdict[key]
                try:
                    month = int(month)
                except ValueError:
                    # try to map a text month to an int
                    month = MONTH_MAP[month]
                except AttributeError:
                    raise ValueError('month must be an integer or month string')
                else:
                    if month < 1 or month > 12:
                        raise ValueError('month must be an integer in the range 1 to 12, or month string')
                kwargs[key] = month

            # ignore 'weekday', etc.
            elif key in DATETIME_KEYWORDS:
                value = int(mdict[key])
                kwargs[key] = value

        # datetime() requires year/month/day

        # not all timestamps have a year
        if 'year' not in kwargs:
            # we default to this year, which won't be right if this
            # process runs into a new year.
            kwargs['year'] = default_year or now().year

        #log.debug(f'get tzinfo. timezone={timezone}') # DEBUG
        ''' We want to set tzinfo from the timestr if possible.
            Second choice is the timezone= passed to parse_timestamp().
            Last choice is default to a "naive" datetime, with no tzinfo.
        '''
        tzinfo = None

        # if timestr has a timezone, override any timezone param
        if 'timezone' in kwargs:
            tz = kwargs['timezone']
            del kwargs['timezone']
            #log.debug(f'kwargs[timezone]: {tz}') # DEBUG
            if tz:
                timezone = tz
                #log.debug(f'set timezone from kwargs: {timezone}') # DEBUG

        if timezone:
            if timezone.upper() in ['UTC','GMT', 'Z']:
                tzinfo = datetime_timezone.utc
            else:
                tzinfo = parse_timezone(timezone)

        if tzinfo:
            kwargs['tzinfo'] = tzinfo
            #log.debug(f'tzinfo: {tzinfo}')
        #else:
            #log.warning('no tzinfo') # DEBUG

        try:
            timestamp = datetime(**kwargs)
        except ValueError:
            timestamp = None
            log(f'bad datetime values: {repr(kwargs)}')

        return timestamp

    RAW_TIMESTAMP_RES = [
        # iso datetime, which is datetime default
        ISO_DATETIME_RE,

        # short iso datetime with timezone
        r'(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)[ T](?P<hour>\d+):(?P<minute>\d+):(?P<second>\d+)(?P<timezone>.*)',

        # short iso datetime
        r'(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)[ T](?P<hour>\d+):(?P<minute>\d+):(?P<second>\d+)',

        # nginx error log
        # Example: 2019/10/17 12:40:36
        r'(?P<year>\d+)/(?P<month>\d+)/(?P<day>\d+) (?P<hour>\d+):(?P<minute>\d+):(?P<second>\d+)',

        # RFC 850, obsoleted by RFC 1036, Example: Sunday, 06-Nov-94 08:49:37 GMT
        r'(?P<weekday>[A-Za-z]+),\s+(?P<day>\d+)-(?P<month>[A-Za-z]+)-(?P<year>\d+)\s+(?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d)\s+(?P<timezone>.*)',

        # Example: Mon, 27 Apr 2020 15:55:56 GMT
        r'(?P<weekday>[A-Za-z]+),\s(?P<day>\d+)\s+(?P<month>[A-Za-z]+)\s+(?P<year>\d+)\s+(?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d)\s+(?P<timezone>.*)',

        # Example: Tue Jan 15 14:49:13 2019
        r'(?P<weekday>[A-Za-z]+)\s+(?P<month>[A-Za-z]+)\s+(?P<day>\d+)\s+(?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d)\s+(?P<year>\d+)',

        # tor log
        # Example: Oct 28 11:06:55.000
        r'(?P<month>[A-Za-z]+)\s+(?P<day>\d\d)[ T](?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d)\.(?P<microsecond>\d\d\d)',

        # syslog
        # Example: Oct 28 11:06:55
        # same as tor log, but without microseconds
        r'(?P<month>[A-Za-z]+)\s+(?P<day>\d+)[ T](?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d)',

        # Example: '02:07:36 05/08/03 EDT'
        # Different parts of the world interpret this differently so we're going to ignore it
        #r'(?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d) (?P<year>\d\d)/(?P<month>\d+)/(?P<day>\d+) (?P<timezone>.*)',

        # date only
        r'(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)',
        ]

    #log.debug(f'timestr: {repr(timestr)}') # DEBUG

    if not _compiled_timestamps:
        # anchor timestamp formats to start of line and compile them
        for raw_re in RAW_TIMESTAMP_RES:

            # if startswith, only match timestamps at the start of the line
            if startswith and not raw_re.startswith(r'^'):
                compiled_re = re.compile(r'^' + raw_re)
            else:
                compiled_re = re.compile(raw_re)

            _compiled_timestamps.append(compiled_re)

    timestamp = None

    if isinstance(timestr, datetime):
        # save some callers from having to check the type
        timestamp = timestr

    elif isinstance(timestr, date):
        timestr = str(timestr)

    elif isinstance(timestr, bytes):
        timestr = str(timestr)

    if not timestamp:

        if isinstance(timestr, str):
            if startswith:
                timestr = strip_end(timestr)
        else:
            raise ValueError(f'time string must be type str, bytes, or datetime, not {type(timestr)}')

        for timestamp_re in _compiled_timestamps:
            if not timestamp:
                try:
                    match = timestamp_re.search(timestr)
                    if match:
                        timestamp = get_timestamp(match.groupdict(), timezone)

                except Exception as e:
                    log.debug(f'unable to parse timestamp: {timestr}')
                    log.debug(format_exception(e))

    if not timestamp:
        # web log format is a special case (not at start of timestr), so try it last
        try:
            timestamp = LogLine.get_timestamp(timestr)

        except ValueError:
            pass

        except Exception as e:
            log.debug(f'unable to parse timestamp as web log line: {timestr}')
            from solidlibs.python.utils import format_exception
            log.debug(format_exception(e))

    if not timestamp:
        # Example: '02-11-2020 10:20:01'
        # date and time only; month and day can be confused depending if European or USA
        FRM = r'^(?P<day>\d\d)-(?P<month>\d\d)-(?P<year>\d\d\d\d)[ T](?P<hour>\d\d):(?P<minute>\d\d):(?P<second>\d\d).*'
        try:
            match = re.search(FRM, timestr)
            if match:
                timestamp = get_timestamp(match.groupdict(), timezone)

        except ValueError:
            pass

        except AttributeError:
            pass

        except Exception as e:
            log.debug(f'unable to parse timestamp: {timestr}')
            from solidlibs.python.utils import format_exception
            log.debug(format_exception(e))


    if not timestamp:
        raise ValueError(f"no timestamp found: '{timestr}'")

    if timezone:
        # we should have a tzinfo attribute
        try:
            if not timestamp.tzinfo:
                raise Exception(f'tzinfo is None. timestr: {timestr}, timezone={timezone}')
        except AttributeError:
            raise Exception(f'tzinfo not set. timestr: {timestr}, timezone={timezone}')

    return timestamp

def format_time(d):
    ''' Return the item in the ISO 8601 format.

        Args:
            d: Can be:
                 * an instance of a datetime.
                 * an instance of a str that can be parsed by parse_timestamp().
                 * an int or float is seconds since the epoch.

        Returns:
            An ISO 8601 format of the date/time.

        Raises:
            ValueError if 'd' arg is not an instance of str, int, float, or datetime.


        >>> format_time(datetime(2012, 7, 6, 17, 57, 12, 4))
        '2012-07-06 17:57:12.000004'
        >>> format_time('2019-10-17 19:46:30.574Z')
        '2019-10-17 19:46:30.000574+00:00'
        >>> format_time('17/Oct/2019:09:35:52 +0000')
        '2019-10-17 09:35:52+00:00'
        >>> format_time('2019-10-23T17:55:00')
        '2019-10-23 17:55:00+00:00'
        >>> format_time(1571760736.9401658)
        '2019-10-22 16:12:16.940166+00:00'
        >>> format_time(1571760736)
        '2019-10-22 16:12:16+00:00'
        >>> format_time(1571760737)
        '2019-10-22 16:12:17+00:00'

        We're not handling this date string because
        different parts of the world interpret this date differently.
        format_time('02:07:36 05/08/03 EDT')
        '0005-08-03 02:07:36'
    '''

    if d is None:
        raise ValueError

    elif isinstance(d, datetime):
        dt = d

    elif isinstance(d, str):
        dt = parse_timestamp(d, timezone='UTC')

    elif isinstance(d, (float, int)):
        dt = seconds_to_datetime(d)

    else:
        raise ValueError

    return dt.isoformat(sep=' ')

def format_date(date=None):
    ''' Return the date in YYYY-mm-dd format.

        Args:
            date: A tuple or a struct_time.
                  Optional. Defaults to today's date.

        Returns:
            A string of the date in YYYY-mm-dd format.

        If date is not specified or the date is None, formats today's date.
        Time zone is UTC.

        >>> format_date((2012, 7, 6, 17, 57, 12, 4, 188, 0))
        '2012-07-06'
        >>> re.match(r'^\d{4}-\d{2}-\d{2}$', format_date()) is not None
        True
    '''

    if not date:
        date = time.gmtime()
    return time.strftime('%Y-%m-%d', date)

def seconds_human_readable(seconds):
    '''
        Formats seconds in a human readable form.

        Args:
            seconds: Seconds as a float or int.

        Returns:
            The years, months, weeks, days, minutes, hours, and remaining seconds
            in human readable format (e.g., 48 minutes, 2 days, 5 hours, 6 minutes).

        >>> seconds_in_week = seconds_in_day * 7
        >>> seconds_in_year = seconds_in_week * 52
        >>> current = datetime.utcnow()
        >>> hour_ago = current - timedelta(minutes=48, seconds=20)
        >>> seconds = (current - hour_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '48 minutes and 20 seconds'
        >>> hour_ago = current - timedelta(minutes=60)
        >>> seconds = (current - hour_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '1 hour'
        >>> hours_ago = current - timedelta(hours=5, minutes=6)
        >>> seconds = (current - hours_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '5 hours and 6 minutes'
        >>> two_days_ago = current - timedelta(days=2)
        >>> seconds = (current - two_days_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '2 days'
        >>> five_plus_weeks_ago = current - timedelta(days=37)
        >>> seconds = (current - five_plus_weeks_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '1 month and 6 days'
        >>> eight_plus_years_ago = current - timedelta(days=2921)
        >>> seconds = (current - eight_plus_years_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '8 years and 1 day'
        >>> three_years_ago = current - timedelta(days=1095)
        >>> seconds = (current - three_years_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '3 years'

        >>> seconds_human_readable(0)
        '0 seconds'

        >>> seconds_human_readable(-1)
        '11 months, 28 days, 23 hours, 59 minutes and 59 seconds'

    '''

    log.warning('human_readable() should be called directly. stacktrace below.')
    log.stacktrace()

    return human_readable.precise_delta(timedelta(seconds=seconds))

    """ Let someone else maintain this. Delete if unused 2023-03-01
    def format_unit_label(label, units):
        ''' Format the label. '''
        if units == 1:
            status = f'{units} {label}'
        else:
            status = f'{units} {label}s'

        return status

    status = None

    if seconds <= 0:
        status = None

    else:
        seconds_in_week = seconds_in_day * 7
        seconds_in_year = seconds_in_week * 52

        years = seconds // seconds_in_year
        if years > 0:
            years_status = format_unit_label('year', int(years))
            weeks = (seconds % seconds_in_year) // seconds_in_week
            if weeks > 0:
                weeks_status = format_unit_label('week', int(weeks))
                status = f'{years_status}, {weeks_status}'
            else:
                status = years_status

        if status is None:
            weeks = seconds // seconds_in_week
            if weeks > 0:
                weeks_status = format_unit_label('week', int(weeks))
                days = (seconds % seconds_in_week) // seconds_in_day
                if days > 0:
                    days_status = format_unit_label('day', int(days))
                    status = f'{weeks_status}, {days_status}'
                else:
                    status = weeks_status

        if status is None:
            days = seconds // seconds_in_day
            if days > 0:
                days_status = format_unit_label('day', int(days))
                hours = (seconds % seconds_in_day) // seconds_in_hour
                if hours > 0:
                    hours_status = format_unit_label('hour', int(hours))
                    status = f'{days_status}, {hours_status}'
                else:
                    status = days_status

        if status is None:
            hours = seconds // seconds_in_hour
            if hours > 0:
                hours_status = format_unit_label('hour', int(hours))
                minutes = (seconds % seconds_in_hour) // seconds_in_minute
                if minutes > 0:
                    minutes_status = format_unit_label('minute', int(minutes))
                    status = f'{hours_status}, {minutes_status}'
                else:
                    status = hours_status

        if status is None:
            minutes = seconds // seconds_in_minute
            if minutes > 1:
                status = format_unit_label('minute', int(minutes))
            else:
                secs = seconds % seconds_in_minute
                if secs > 0:
                    status = format_unit_label('second', int(secs))

    return status
    """

def timedelta_to_human_readable(td, verbose=True):
    ''' Formats a timedelta in a human readable form.

        Args:
            td:      A timedelta produced by datetime.timedelta.
            verbose: If True, includes full words for timeperiods (e.g., hour).
                     If False, includes abbreviation for timeperiods (e.g., hr.).
                     Optional. Defaults to True.

        Returns:
            A human readable form of the timedelta (e.g.,
            2 days, 2 hours, 6 minutes, 3 seconds).
            If total time is less than a second, then shows milliseconds
            instead of microseconds. Otherwise, rounds to the nearest second.

        >>> timedelta_to_human_readable(timedelta(days=1, seconds=123, minutes=4, hours=26))
        '2 days, 2 hours, 6 minutes and 3 seconds'
        >>> timedelta_to_human_readable(timedelta(seconds=123))
        '2 minutes and 3 seconds'
        >>> timedelta_to_human_readable(timedelta(seconds=65))
        '1 minute and 5 seconds'
        >>> timedelta_to_human_readable(timedelta(milliseconds=85))
        '0.09 seconds'
        >>> timedelta_to_human_readable(timedelta(days=1, seconds=123, minutes=4, hours=26), verbose=False)
        '2d, 2h, 6m and 3s'
        >>> timedelta_to_human_readable(timedelta(seconds=123), verbose=False)
        '2m and 3s'
        >>> timedelta_to_human_readable(timedelta(seconds=65), verbose=False)
        '1m and 5s'
        >>> timedelta_to_human_readable(timedelta(milliseconds=85), verbose=False)
        '0.09s'
    '''

    log.warning('human_readable() should be called directly. stacktrace below.')
    log.stacktrace()

    if not verbose:
        human_readable.i18n.activate('en_ABBR')
    return human_readable.precise_delta(td)

    """ Let someone else maintain this. Delete if unused 2023-03-01
    tdString = ''

    if td.days or td.seconds:

        # days
        if td.days:
            tdString = f'{td.days} day{s_if_plural(td.days)}'

        # round seconds
        seconds = td.seconds
        if (td.microseconds * 2) >= td.max.microseconds:
            seconds = seconds + 1

        # hours
        hours = seconds // seconds_in_hour
        if hours:
            if tdString:
                tdString = tdString + ', '
            tdString = tdString + f'{hours} hour{s_if_plural(hours)}'

        # minutes
        secondsLeft = seconds - (hours * seconds_in_hour)
        if secondsLeft:
            minutes = secondsLeft // seconds_in_minute
            if minutes:
                if tdString:
                    tdString = tdString + ', '
                tdString = tdString + f'{minutes} minute{s_if_plural(minutes)}'
                secondsLeft = secondsLeft - (minutes * seconds_in_minute)

        # seconds
        if secondsLeft:
            if tdString:
                tdString = tdString + ', '
            tdString = tdString + f'{secondsLeft} second{s_if_plural(secondsLeft)}'

    else:
        milliseconds = (td.microseconds + 1) / 1000
        tdString = f'{milliseconds} ms'

    if not verbose:
        m = re.match('.*( day)', tdString)
        if m:
            tdString = tdString.replace(m.group(1), ' day')

        m = re.match('.*( hour)', tdString)
        if m:
            tdString = tdString.replace(m.group(1), ' hr')

        m = re.match('.*( minute)', tdString)
        if m:
            tdString = tdString.replace(m.group(1), ' min')

        m = re.match('.*( second)', tdString)
        if m:
            tdString = tdString.replace(m.group(1), ' sec')

        tdString = tdString.replace(',', '')

    return tdString
    """


def get_short_date_time(date_time):
    '''Format the date-time without seconds.

        Args:
            date_time: A python datetime. Any other type will return an empty string.

        Returns:
            A string with the date time in YYYY-mm-dd HH:MM format.

        >>> get_short_date_time(datetime(2012, 6, 1, 12, 30, 0))
        '2012-06-01 12:30'
        >>> get_short_date_time(datetime(2012, 6, 1, 12, 30, 41))
        '2012-06-01 12:30'
        >>> get_short_date_time(datetime(2012, 6, 1, 12, 30, 0, 0))
        '2012-06-01 12:30'
        >>> get_short_date_time(None)
        ''
    '''

    if date_time:
        new_date_time = date_time.isoformat(sep=' ')
        try:
            m = re.match(r'.*?(\d+\:\d+\:\d+).*', new_date_time)
            if m:
                current_time = m.group(1)
                index = current_time.rfind(':')
                new_date_time = new_date_time.replace(m.group(1), current_time[:index])
                index = new_date_time.rfind('.')
                if index > 0:
                    new_date_time = new_date_time[:index]
        except Exception:
            pass

    else:
        new_date_time = ''

    return new_date_time

def datetime_to_date(dt):
    ''' Converts a datetime to a date. If dt is a date, returns a copy.

        Args:
            dt: A python datetime.datetime structure.

        Returns:
            A python datetime.date structure.

        >>> datetime_to_date(datetime(2012, 6, 1, 12, 30, 0))
        datetime.date(2012, 6, 1)
        >>> datetime_to_date(datetime(2012, 6, 1, 12, 30, 0, 0))
        datetime.date(2012, 6, 1)
    '''
    return date(dt.year, dt.month, dt.day)

def date_to_datetime(d):
    ''' Converts a date or datetime to a datetime at the beginning of the day.

        Args:
            d: A python datetime.date structure.

        Returns:
            A python datetime.datetime structure with a UTC timezone.

        >>> date_to_datetime(datetime(2012, 6, 1, 1, 39))
        datetime.datetime(2012, 6, 1, 0, 0, tzinfo=datetime.timezone.utc)
        >>> date_to_datetime(date(2012, 6, 1))
        datetime.datetime(2012, 6, 1, 0, 0, tzinfo=datetime.timezone.utc)
    '''

    return datetime(d.year, d.month, d.day, tzinfo=datetime_timezone.utc)

def timedelta_to_days(td):
    ''' Converts timedelta to floating point days.

        Args:
            td: A python datetime.timedelta.

        Returns:
            The days in a floating point format (e.g., 5.3 days).

        >>> timedelta_to_days(timedelta(seconds=864000))
        10.0
        >>> timedelta_to_days(timedelta(days=4, seconds=43200))
        4.5
    '''

    return timedelta_to_seconds(td) / seconds_in_day

def timedelta_to_seconds(td):
    ''' Converts timedelta to floating point seconds.

        Alternative: datetime.timedelta.total_seconds().

        Args:
            td: A python datetime.timedelta.

        Returns:
            The seconds since the epoch in a floating point format.

        >>> timedelta_to_seconds(timedelta(seconds=864000))
        864000.0
        >>> timedelta_to_seconds(timedelta(days=4, seconds=43200))
        388800.0
        >>> timedelta_to_seconds(timedelta())
        0.0
    '''

    # internally timedelta only stores days, seconds, and microseconds
    ts = (
        (td.days * seconds_in_day) +
        td.seconds +
        ((1.0 * td.microseconds) / microseconds_in_second))

    return ts

def datetime_to_seconds(dt):
    ''' Converts datetime to floating point seconds.

        Args:
            dt: A python datetime.datetime.

        Returns:
            The seconds since the epoch in a floating point format (e.g., 0.0).

        >>> dt = datetime(2012, 6, 1, 12, 30, 0)
        >>> secs = calendar.timegm(dt.timetuple())
        >>> secs
        1338553800
        >>> dt_secs = datetime_to_seconds(dt)
        >>> dt_secs == secs
        True
    '''

    return calendar.timegm(dt.timetuple())

def seconds_to_datetime(seconds):
    ''' Convert seconds since the epoch to a datetime.

        Convenience function.

        Args:
            seconds: Seconds since the epoch.

        Returns:
            The equivalent in datetime.datetime with the UTC timezone.

        >>> seconds_to_datetime(864000)
        datetime.datetime(1970, 1, 11, 0, 0, tzinfo=datetime.timezone.utc)
    '''

    utc = datetime_timezone.utc
    return datetime.fromtimestamp(float(seconds), tz=utc)

def one_month_before(the_date):
    ''' Returns one month before.

        Args:
            the_date: A datetime.date or datetime.datetime.

        Returns:
            The datetime.datetime one month before the arg.
            If the arg is a datetime.date, then the timezone is set to UTC.

        >>> one_month_before(date(2012, 6, 1))
        datetime.datetime(2012, 5, 1, 0, 0, tzinfo=datetime.timezone.utc)
        >>> one_month_before(date(2012, 3, 30))
        datetime.datetime(2012, 2, 29, 0, 0, tzinfo=datetime.timezone.utc)
        >>> one_month_before(date(2012, 5, 31))
        datetime.datetime(2012, 4, 30, 0, 0, tzinfo=datetime.timezone.utc)
    '''

    if the_date.month > 1:
        last_year = the_date.year
        last_month = the_date.month - 1
    else:
        last_year = the_date.year - 1
        last_month = 12

    current_date_range = calendar.monthrange(the_date.year, the_date.month)
    last_date_range = calendar.monthrange(last_year, last_month)
    if the_date.day == current_date_range[1]:
        last_day = last_date_range[1]
    else:
        if the_date.day > last_date_range[1]:
            last_day = last_date_range[1]
        else:
            last_day = the_date.day

    if isinstance(the_date, date):
        earlier = datetime(last_year, last_month, last_day, tzinfo=datetime_timezone.utc)
    else:
        earlier = datetime(last_year, last_month, last_day)

    return earlier

def start_of_day(d):
    ''' Returns datetime with no hours, minutes, seconds, or microseconds.

        Args:
            d: A datetime.date or datetime.datetime.

        Returns:
            The datetime.datetime at 00:00.

        >>> start_of_day(date(2012, 6, 1))
        datetime.datetime(2012, 6, 1, 0, 0, tzinfo=datetime.timezone.utc)
        >>> start_of_day(datetime(2012, 3, 30, 11, 27))
        datetime.datetime(2012, 3, 30, 0, 0, tzinfo=datetime.timezone.utc)
    '''

    return date_to_datetime(datetime_to_date(d))

def end_of_day(d):
    ''' Returns the latest datetime for the day.

        Args:
            d: A datetime.date or datetime.datetime.

        Returns:
            The datetime.datetime at 59:59.999999.

        >>> end_of_day(date(2012, 6, 1))
        datetime.datetime(2012, 6, 1, 23, 59, 59, 999999, tzinfo=datetime.timezone.utc)
        >>> end_of_day(datetime(2012, 3, 30, 11, 27))
        datetime.datetime(2012, 3, 30, 23, 59, 59, 999999, tzinfo=datetime.timezone.utc)
    '''

    return start_of_day(d) + one_day - one_microsecond

def date_range(start, end, lei_convention=False):
    ''' Generates every date in the range from start to end, inclusive.

        Args:
            start:          The start of the range of dates in datetime.date or datetime.datetime
                            format. If start is later than end, returns dates in reverse
                            chronological order.
            end:            The end of the range of dates in datetime.date or datetime.datetime format.
            lei_convention: Set lei_convention=True if you wan t to follow the endpoint
                            convention [a, b) and exclude the right endpoint, i.e. include
                            the first element and exclude the last.
                           . See http://mathworld.wolfram.com/Interval.html

        Returns:
            Every date in the range from start to end, inclusive, unless lei_convention is
            set to True.

        >>> list(date_range(date(2012, 6, 1), date(2012, 6, 2)))
        [datetime.date(2012, 6, 1), datetime.date(2012, 6, 2)]
        >>> list(date_range(date(2012, 6, 2), date(2012, 6, 1)))
        [datetime.date(2012, 6, 2), datetime.date(2012, 6, 1)]
        >>> list(date_range(date(2012, 6, 1), date(2012, 6, 1)))
        [datetime.date(2012, 6, 1)]
        >>> list(date_range(date(2012, 6, 1), date(2012, 6, 2), lei_convention=True))
        [datetime.date(2012, 6, 1)]
        >>> list(date_range(date(2012, 6, 2), date(2012, 6, 1), lei_convention=True))
        [datetime.date(2012, 6, 2)]
        >>> list(date_range(datetime(2012, 6, 1, 21, 3), datetime(2012, 6, 2, 0, 0)))
        [datetime.date(2012, 6, 1), datetime.date(2012, 6, 2)]
        >>> list(date_range(datetime(2012, 6, 1, 0, 0), datetime(2012, 6, 2, 23, 59, 59, 999999)))
        [datetime.date(2012, 6, 1), datetime.date(2012, 6, 2)]
        >>> list(date_range(datetime(2012, 6, 2, 23, 59, 59, 999999), datetime(2012, 6, 1, 23, 59, 59, 999999)))
        [datetime.date(2012, 6, 2), datetime.date(2012, 6, 1)]
        >>> list(date_range(datetime(2012, 6, 1, 0, 0), datetime(2012, 6, 1, 23, 59, 59, 999999)))
        [datetime.date(2012, 6, 1)]
    '''

    increasing = start <= end
    day = datetime_to_date(start)

    if lei_convention:
        if increasing:
            if isinstance(end, datetime):
                end = end - one_microsecond
            else:
                end = end - one_day
        else:
            if isinstance(end, datetime):
                end = end + one_microsecond
            else:
                end = end + one_day

    @contextmanager
    def wait(self, timeout):
        ''' Context manager to wait for a timeout. Log exceptions.

            Args:
                timeout: in seconds.
        '''

        log(f'wait {timeout} seconds')

        with log.exceptions():
            yield

def strip_end(timestr):
    ''' Strip the non-timestamp part of the string.

        Args:
            A string with the timestamp at the beginning of the string.

        Returns:
            A string with just the timestamp.

        >>> timestr = '2021-07-11 09:32:00.000.json'
        >>> strip_end(timestr)
        '2021-07-11 09:32:00.000'
        >>> timestr = '2021-07-12 10:11:00.000+00:00'
        >>> strip_end(timestr)
        '2021-07-12 10:11:00.000+00:00'
        >>> timestr = '2021-07-14 12:42:00.000Z.json'
        >>> strip_end(timestr)
        '2021-07-14 12:42:00.000Z'
    '''

    end = len(timestr)
    for index in range(len(timestr)):

        # ignore these characters
        ok = (timestr[index] == ' ' or
              timestr[index] == '-' or
              timestr[index] == ':' or
              timestr[index] == '.' or
              timestr[index] == '+' or
              timestr[index] == 'T' or
              timestr[index] == 'Z')

        if not ok:
            try:
                # otherwise, verify only numbers ok
                int(timestr[index])
            except:             # pylint:bare-except -- catches more than "except Exception"
                end = index -1
                break

    timestr = timestr[:end]
    if timestr.endswith('.'):
        timestr = timestr[:len(timestr)-1]

    return timestr

def date_string_to_date(date_string):
    ''' Convert a string representation of a date into a python date.

        Args:
            date_string: A string representation of a date.

        Returns:
            The equivalent in datetime.date format.

        >>> date_string_to_date('2015-04-25')
        datetime.date(2015, 4, 25)
        >>> date_string_to_date('14-01-2015')
        datetime.date(2015, 1, 14)
        >>> date_string_to_date('test')
    '''

    Date_Format1 = r'(\d{4})-(\d{2})-(\d{2})'
    Date_Format2 = r'(\d{2})-(\d{2})-(\d{4})' # the European alternative

    d = None
    m = re.match(Date_Format1, date_string)
    if m:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    else:
        m = re.match(Date_Format2, date_string)
        if m:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    return d

def datetime_string_to_datetime(date_string):
    ''' Deprecated. Use parse_timestamp(). '''

    raise DeprecationWarning('Use parse_timestamp() instead of datetime_string_to_datetime()')

    return parse_timestamp()


# be careful about using the following values
# they are calculated when this module is imported
today = now()
tomorrow = now() + one_day
yesterday = now() - one_day
one_month_ago = one_month_before(today)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
