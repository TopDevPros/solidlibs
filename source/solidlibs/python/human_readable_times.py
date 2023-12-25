'''
    Human Readable Times.

    Copyright 2009-2023 TopDevPros
    Last modified: 2023-08-27

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import human_readable
from datetime import date, datetime, timedelta
from solidlibs.python.log import Log
from solidlibs.python.times import seconds_in_day


log = Log()

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

    if not verbose:
        human_readable.i18n.activate('en_ABBR')
    return human_readable.precise_delta(td)

if __name__ == "__main__":
    import doctest
    doctest.testmod()
