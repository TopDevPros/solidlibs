'''
    Log Django debug pages.

    Copyright 2010-2023 solidlibs
    Last modified: 2023-05-17
    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import os
from tempfile import NamedTemporaryFile

try:
    from django.utils.deprecation import MiddlewareMixin
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

from solidlibs.django_addons.utils import is_django_error_page
#from solidlibs.python.format import pretty
from solidlibs.python.log import Log

log = Log()


class DebugMiddleware(MiddlewareMixin):
    ''' Write to debugging log.

        Logs Django debug pages and says it's an error. '''

    def process_exception(self, request, exception):
        log('process_exception()')
        # request does not include a kwarg named PATH
        log(f'request: {request}')
        log(exception)

    def process_response(self, request, response):

        def log_why(why):
            log(why)
            log(f'request: {request!r}')
            #log.debug(f'    headers:\n{pretty(request.META)}')
            #log.debug(f'    data: {repr(request.POST)}')
            log(f'response: {response!r}')

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
