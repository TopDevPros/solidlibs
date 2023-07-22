'''
    Retry 404 response on another backend http server.

    If static resources such as css and js are served by a front end server,
    that static server must also serve the static resources of the other
    backend http server. See redirect404.py for an alternative. Or you may
    choose to bypass the front end server, at a cost in performance.

    The server is specified by settings.PROXY_404_SERVER.
    PROXY_404_SERVER is in the form:

        [USERNAME[:PASSWORD]@]HOST[:PORT]

    HOST can be a DNS name or IP address.
    PROXY_404_SERVER Examples::

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

import traceback
import urllib.request
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


class Proxy404Middleware(MiddlewareMixin):

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

                old_host = request.get_host()
                new_host = settings.PROXY_404_SERVER
                if new_host != old_host:

                    log(f'old host: {old_host}, new host: {new_host}') #DEBUG
                    new_url = urlunsplit([scheme, new_host,
                        parts.path, parts.query, parts.fragment])
                    log(f'url: {url}') #DEBUG
                    log(f'parts: {parts}')) #DEBUG
                    log(f'new url: {new_url}') #DEBUG

                    try:
                        log(f'opening {new_url}') #DEBUG
                        stream = urllib.request.urlopen(new_url)
                        log(f'reading {new_url}') #DEBUG
                        try:
                            new_response = http.HttpResponse(stream.read())
                        finally:
                            stream.close()
                        if new_response.status_code == 404:
                            log(f'404 {new_url}') #DEBUG
                        else:
                            log(f'got {new_url}') #DEBUG
                            response = new_response

                    except Exception:
                        # just log it and return the exsting 404
                        log(f'url: {url}')
                        log(f'parts: {parts}')
                        log(f'new url: {new_url}')
                        log(traceback.format_exc())

        except Exception:
            log(traceback.format_exc())
            raise

        return response
