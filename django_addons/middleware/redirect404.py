'''
    Redirect 404 response to another http server.

    The server is specified by settings.REDIRECT_404_SERVER.
    REDIRECT_404_SERVER is in the form:

        [USERNAME[:PASSWORD]@]HOST[:PORT]

    HOST can be a DNS name or IP address.
    REDIRECT_404_SERVER Examples::

        example.com
        example.com:8080
        username@example.com:8080
        username:password@example.com:8080
        127.0.0.1
        127.0.0.1:8080

    Copyright 2014-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

from traceback import format_exc
from urllib.parse import urlsplit, urlunsplit

try:
    from django import http
    from django.conf import settings
    from django.utils.deprecation import MiddlewareMixin
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

from solidlibs.python.log import Log

log = Log()


class Redirect404Middleware(MiddlewareMixin):

    def process_response(self, request, response):

        try:
            if response.status_code == 404:

                log('got 404')
                url = request.get_full_path()
                parts = urlsplit(url)

                if parts.scheme == '':
                    if request.is_secure():
                        scheme = 'https'
                    else:
                        scheme = 'http'
                else:
                    scheme = parts.scheme
                new_host = settings.REDIRECT_404_SERVER

                new_url = urlunsplit([scheme, new_host,
                    parts.path, parts.query, parts.fragment])

                try:
                    response = http.HttpResponsePermanentRedirect(new_url)

                except Exception:
                    # just log it and return the exsting 404
                    log(f'url: {url}')
                    log('parts: %s' % repr(parts))
                    log(f'new url: {new_url}')

        except Exception:
            log(format_exc())
            raise

        return response
