'''
    Log Django debug pages.

    Copyright 2010-2023 TopDevPros
    Last modified: 2023-12-07

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import os
from pprint import PrettyPrinter
from tempfile import NamedTemporaryFile

try:
    from django.utils.deprecation import MiddlewareMixin
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

from solidlibs.django_addons.utils import is_django_error_page
from solidlibs.python.log import Log

log = Log()
pretty = PrettyPrinter(indent=4).pprint


class DebugMiddleware(MiddlewareMixin):
    ''' Write to debugging log.

        Logs Django debug pages and says if it's an error. '''

    def process_exception(self, request, exception):
        log('process_exception()')
        # request does not include a kwarg named PATH
        log(f'request:\n\t{request}')
        log(exception)

    def process_response(self, request, response):

        def log_why(why):
            log(f'request: {why}')
            log(f'request: {pretty(request)}')
            log(f'response: {pretty(response)}')

        try:
            if is_django_error_page(response.content):
                with NamedTemporaryFile(
                    prefix='django.debug.page.', suffix='.html',
                    delete=False) as htmlfile:
                    htmlfile.write(response.content)
                os.chmod(htmlfile.name, 0o644)
                log(f'django app error: django debug page at {htmlfile.name}')

            elif response.status_code == 403:
                log.warning(f'http error {response.status_code}: missing csrf token?')
                log_why(f'http error {response.status_code}')

            elif response.status_code >= 400:
                log_why(f'http error {response.status_code}')
                #log.stacktrace()

        except AttributeError as ae:
            log(f'ignored in solidlibs.django_addons.middleware.DebugMiddleware.process_response(): {ae}')

        return response


class DebugDetailsMiddleware(DebugMiddleware):
    ''' Write debugging details to log. '''

    def process_response(self, request, response):

        if request.META:
            pretty_dictlike(request.META)

        if response.status_code != 200:
            log(f'response statuscode: {response.status_code}')
            if response.reason_phrase:
                log(f'response reason: {response.reason_phrase}')

        if response.headers:
            pretty_dictlike(response.headers)
        try:
            if response.content:
                pretty(response.content)
                #log('formatted content')
        except AttributeError:
            log('response has no content; streaming content?')

        return response

def pretty_dictlike(meta):
    ''' django uses some "dict-like" objects. '''

    s = ''
    for key in meta:
        if s:
            s += '\n'
        s += f'    {key}: {meta[key]}\n'

    return s
