'''
    Log conversion events.

    Copyright 2009-2023 TopDevPros
    Last modified: 2023-10-04
'''

import os
import re
from datetime import datetime
from urllib.parse import quote, urlencode

from django.conf import settings

from solidlibs.django_addons.utils import get_remote_ip
from solidlibs.net.browser import is_known_bot, is_known_harvester, is_known_spammer, get_agent_info
from solidlibs.net.http_addons import get_agent_referer
from solidlibs.python.log import Log
from solidlibs.python.utils import last_exception, object_name

Unknown_Agent_Prefix = 'unknown'

log = Log()
debug = True


def log_event(name, logfile=None, request=None, user_agent=None, details=None):
    ''' Log an event.

        An event is an activity, such as viewing a web page or receiving
        an email about a complete sale, that will help us see whether a user
        is interested in our product, web site, etc.

        If we're conducting an A/B test, a web server such as nginx has
        no way of knowing that different users may see different pages
        for the same URL. If you log the event, then there is a record
        of which variant the user saw.

        If you receive email everytime a user completes an order and that email
        contains critical details such as IP address, user agent, etc. then you
        can log that event to aid in the analysis of that's user's interest.

        The event log files should be read after log files
        produced by the web server. This virtual access log entry may
        have the same time stamp as the access that invoked this
        function, and we want this entry to appear after the real one
        in any analyses.

        We don't just redir and let the web server do this because
        the redir is too slow and noisy in the UI.
        '''

    if logfile is None:
        logfile = get_event_log_file()

    try:
        user_agent, referer = get_agent_referer(request=request, user_agent=user_agent)

        if user_agent is not None:
            browser_name = browser_version = other = ''
        else:
            browser_name, browser_version, other = get_agent_info(user_agent)

        # encode as utf
        if user_agent:
            user_agent = user_agent
        if details:
            for key in details:
                details[key] = details[key]

        entry = get_entry(name, request=request, user_agent=user_agent, details=details)
        # don't log bots, etc., although POSTs from our users will appear to be a bot so accept those
        if ('POST ' not in entry and
            (is_known_bot(browser_name, other) or
             is_known_harvester(user_agent) or
             is_known_spammer(referer)) ):
            pass

        else:
            #log(entry)

            # create the subdirs if they don't exist
            parent_dir = os.path.dirname(logfile)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, 660)

            log_file = open(logfile, 'a+')
            log_file.write(f'{entry}\n')
            log_file.close()
    except:
        exception = last_exception()
        log(exception)
        log_if_possible(f'log_entry request: {request}')
        log_if_possible(f'log_entry user_agent: {user_agent}')
        log_if_possible(f'log_entry details: {details}')

def log_bad_form(request, form, event_label, logfile=None, form_name=None):
    '''Track the bad fields entered.'''

    if form_name is None:
        form_name = 'form'

    # get details of invalid signup
    details = {}
    # see django.contrib.formtools.utils.security_hash()
    # for example of form traversal
    for field in form:
        if (hasattr(form, 'cleaned_data') and
            field.name in form.cleaned_data):
            name = field.name
        else:
            # mark invalid data
            name = '__invalid__' + field.name
        details[name] = field.data
    if len(details) <= 0:
        details[form_name] = 'empty'
    else:
        if form_name == 'form':
            subject = 'Bad form'
        else:
            subject = f'Bad {form_name} form'
        log(f'Bad form: {form}')

    log_event(event_label, request=request, details=details)
    try:
        if form.name.errors:
            log('  ' + form.name.errors)
        if form.email.errors:
            log('  ' + form.email.errors)
    except:
        pass

def get_entry(name, request=None, user_agent=None, when=None, details=None):
    ''' Build a simulated Apache log entry.

        The log entry is in Apache server log format.

        Example log line:
        67.195.115.61 www.codeberg.com/topdevpros - [08/Nov/2009:06:31:25 +0000] "GET /robots.txt HTTP/1.0" 301 0 "-" "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)"

        If request is missing or None:
            ip = '0.0.0.0'
            host = 'no_host'
            method = 'GET'
            protocol = 'HTTP'

        In these tests we should really be checking if LogParser can parse the events.

        >>> when = '07/Oct/2010:18:19:42 +0000'
        >>> get_entry('test url/page', when=when)
        '0.0.0.0 no_host - [07/Oct/2010:18:19:42 +0000] "GET test%20url/page HTTP" 200 0 "-" "no_user_agent"'
        >>> get_entry('test url/page', user_agent='test user agent', when=when)
        '0.0.0.0 no_host - [07/Oct/2010:18:19:42 +0000] "GET test%20url/page HTTP" 200 0 "-" "test user agent"'
        >>> get_entry('test url/page', details={'param1': '1', 'param2': '2'}, when=when)
        '0.0.0.0 no_host - [07/Oct/2010:18:19:42 +0000] "GET test%20url/page?param2=2&param1=1 HTTP" 200 0 "-" "no_user_agent"'
        >>> get_entry('test url/page', user_agent='test user agent', details={'param1': '1', 'param2': '2'}, when=when)
        '0.0.0.0 no_host - [07/Oct/2010:18:19:42 +0000] "GET test%20url/page?param2=2&param1=1 HTTP" 200 0 "-" "test user agent"'

    '''

    name = quote(name)

    # if we're using a reverse proxy, the ip is the proxy's ip address
    if request:
        ip = get_remote_ip(request)

        host = request.META['SERVER_NAME']
        method = request.META['REQUEST_METHOD']

        if request.is_secure():
            protocol = 'HTTPS/1.1'
        else:
            protocol = 'HTTP/1.1'

    else:
        ip = '0.0.0.0'
        host = 'no_host'
        method = 'GET'
        protocol = 'HTTP'

    time_zone = datetime.now().strftime('%z')
    if not time_zone:
        time_zone = '+0000'
    if not when:
        when = f"{datetime.now().strftime('%d/%b/%Y:%H:%M:%S')} {time_zone}"

    if details:
        query = urlencode(details)
        url = f'{name}?{query}'
    else:
        url = name

    if not user_agent:
        try:
            _, _, entry = object_name(get_entry).rpartition('.')
            user_agent = f'{Unknown_Agent_Prefix} {entry}/1.0'
        except:
            user_agent = f'{Unknown_Agent_Prefix} {object_name(get_entry)}/1.0'

    try:
        log_entry = ('{} {} - [{}] "{} {} {}" 200 0 "-" "{}"'.format(
                     ip, host, when, method, url, protocol, user_agent))
    except UnicodeDecodeError:
        log_if_possible(f'get_entry name: {name}')
        log_if_possible(f'get_entry ip: {ip}')
        log_if_possible(f'get_entry host: {host}')
        log_if_possible(f'get_entry when: {when}')
        log_if_possible(f'get_entry method: {method}')
        log_if_possible(f'get_entry url: {url}')
        log_if_possible(f'get_entry method: {protocol}')
        log_if_possible(f'get_entry url: {user_agent}')
        log_entry = ('{} {} - [{}] "{} {} {}" 200 0 "-" " "'.format(
                     ip, host, when, method, url, protocol))

    return log_entry


def get_event_log_file():
    '''
        Get the directory where events will be logged.

        Ideally, this will be in the subdirectory "conversions"
        under the project's DATA_DIR. If the project's settings
        does not define the DATA_DIR constant, then it tries
        to to create the "conversions" subdirectory in the
        project's BASE_DIR. If that fails, then it tries the
        current working directory.

        Return:
            the full path of the event log
    '''

    try:
        data_dir = settings.DATA_DIR
    except AttributeError:
        try:
            data_dir = settings.BASE_DIR
        except AttributeError:
            data_dir = os.getcwd()

    default_log_dir = os.path.join(data_dir, 'conversions')
    if os.path.exists(default_log_dir):
        log_dir = default_log_dir
    else:
        try:
            os.makedirs(default_log_dir)
            log_dir = DEFAULT_LOG_DIR
        except PermissionError:
            log_dir = data_dir

    log_file = os.path.join(log_dir, 'events.log')

    return log_file

def log_if_possible(message):
    ''' Log inside a try in case there's an error. '''

    try:
        log(message)
    except UnicodeDecodeError as ude:
        log(ude)

if __name__ == "__main__":
    import doctest
    doctest.testmod()

