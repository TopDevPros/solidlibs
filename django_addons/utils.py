'''
    Utility classes and functions.

    Copyright 2009-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import os
import os.path
import re
import sys
from traceback import format_exc
from urllib.parse import urljoin

try:
    from django.conf import settings
    from django.db.models import CharField, EmailField
    from django.utils.encoding import DjangoUnicodeDecodeError
except ModuleNotFoundError:
    sys.exit('Django required')

from solidlibs.python.log import Log
from solidlibs.python.utils import is_string


log = Log()

def is_secure_connection(request):
    ''' Check if connection is secure.

        >>> from django.test import RequestFactory
        >>> factory = RequestFactory()
        >>> request = factory.get('https://127.0.0.1/bitcoin/')
        >>> request.META['HTTP_X_SCHEME'] = 'https'
        >>> is_secure_connection(request)
        True

        >>> from django.test import RequestFactory
        >>> factory = RequestFactory()
        >>> request = factory.get('https://127.0.0.1/bitcoin/')
        >>> request.META['wsgi.url_scheme'] = 'https'
        >>> is_secure_connection(request)
        True

        >>> from django.test import RequestFactory
        >>> factory = RequestFactory()
        >>> request = factory.get('http://127.0.0.1/bitcoin/')
        >>> is_secure_connection(request)
        False
    '''

    secure = False
    try:
        if 'HTTP_X_SCHEME' in request.META:
            secure = request.META['HTTP_X_SCHEME'] == 'https'
        elif 'wsgi.url_scheme' in request.META:
            secure = request.META['wsgi.url_scheme'] == 'https'
    except Exception:
        log(format_exc())

    return secure

def get_websocket_url(request):
    '''
        Get the websocket url based on the http connection.

        >>> from django.test import RequestFactory
        >>> factory = RequestFactory()
        >>> request = factory.get('https://127.0.0.1/bitcoin/')
        >>> request.META['HTTP_X_SCHEME'] = 'https'
        >>> get_websocket_url(request)
        'wss://127.0.0.1'

        >>> from django.test import RequestFactory
        >>> factory = RequestFactory()
        >>> request = factory.get('http://127.0.0.1/bitcoin/')
        >>> get_websocket_url(request)
        'ws://127.0.0.1'
    '''

    if 'HTTP_HOST' in request.META:
        host = request.META['HTTP_HOST']
    elif 'REMOTE_ADDR' in request.META:
        host = request.META['REMOTE_ADDR']
    else:
        host = None

    if host:
        if is_secure_connection(request):
            url = f'wss://{host}'
        else:
            url = f'ws://{host}'
    else:
        url = None

    return url

def django_error_page_response(request, error=None):
    ''' Return a response with Django's error page.

        If settings.DEBUG is True, Django automatically shows a useful
        error page for exceptions in views. But sometimes an exception
        isn't propogated out of the view, such as when the exception
        occurs in a separate thread. This shows the Django error page
        for any exception.

        If error is not present or is None, returns an error page for the
        last exception.

        Example:
            error = None
            ...
            # in separate thread
            error = sys.exc_info()
            ...
            # in parent thread
            show_django_error_page(error)
        '''

    from django.views.debug import technical_500_response       # pylint: disable=import-outside-toplevel
    # error should be sys.exc_info() from an earlier except block
    if not error:
        error = sys.exc_info()
    exc_type, exc_value, tb = error
    response = technical_500_response(request, exc_type, exc_value, tb)

    return response


def is_django_error_page(html):
    ''' Returns True if this html contains a Django error page,
        else returns False.'''

    django_error_1 = b"You're seeing this error because you have"
    django_error_2 = b'display a standard 500 page'

    try:
        smart_html = html #smart_text(html)
    except DjangoUnicodeDecodeError:
        # definitely not a django html error page
        result = False
    else:
        result = (django_error_1 in smart_html) and (django_error_2 in smart_html)

    return result

def get_json_dir():
    '''
        Get the directory name where json output from the database are stored.

        >>> dirname = get_json_dir()
        >>> dirname.endswith('data/json')
        True
    '''

    return  os.path.join(settings.DATA_DIR, 'json')

def first_instance(model):
    ''' Return first instance of a model, or None if none.

        When django insists on a default for a ForeignKey field definition, this works.
        Because the function in default=function can't have any params, use something like::

            class MyModel(Model)

                ...

                def other_model_default():
                    return first_instance(MyOtherModel)

        >>> from django.contrib.sites.models import Site
        >>> from django.core.management import call_command
        >>> sites = Site.objects.all()
        >>> if len(sites) > 0:
        ...     for site in sites:
        ...         __ = site.delete()
        >>> CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
        >>> fixture_name = os.path.join(CURRENT_DIR, 'fixtures', 'sites.site.json')
        >>> call_command("loaddata", f"{fixture_name}", verbosity=0)
        >>> first_instance(Site)
        <Site: test.com>
    '''

    objects = None
    default_object = None

    try:
        objects = model.objects.filter(is_active=True)
        log(objects)
    except Exception:
        try:
            objects = model.objects.all()
            for obj in objects.order_by('pk'):
                log(obj.pk)
        except Exception:
            log(format_exc())

    if objects:
        if len(objects) > 0:
            objects = objects.order_by('pk')
            default_object = objects[0]

    return default_object

def get_remote_ip(request):
    '''
        Get the remote ip. If there is a forwarder, assume the first IP
        address (if there are more than 1) is the original machine's address.

        Otherwise, use the remote addr.

        Any errors, return 0.0.0.0

        >>> from django.test import RequestFactory
        >>> factory = RequestFactory()
        >>> request = factory.get('https://127.0.0.1/bitcoin/')
        >>> get_remote_ip(request)
        '127.0.0.1'
    '''

    Unknown_IP = '0.0.0.0'

    if request:
        try:
            # if we're using a reverse proxy, the ip is the proxy's ip address
            remote_addr = request.META.get('REMOTE_ADDR', '')
            forwarder = request.META.get('HTTP_X_FORWARDED_FOR', '')
            if forwarder and forwarder is not None and len(forwarder) > 0:
                m = re.match('(.*?),.*?', forwarder)
                if m:
                    remote_ip = m.group(1)
                else:
                    remote_ip = forwarder
            else:
                remote_ip = remote_addr

            if not remote_ip or remote_ip is None or len(remote_ip) <= 0:
                remote_ip = Unknown_IP
        except Exception:
            log(format_exc())
            remote_ip = Unknown_IP
    else:
        remote_ip = Unknown_IP
        log('no request so returning unknown ip address')

    return remote_ip

def get_absolute_url(url, home_url, request=None):
    '''
        Return an absolute url from a relative url
        adapting for protocol if request included.

        >>> get_absolute_url('bitcoin', 'http://127.0.0.1')
        'http://127.0.0.1/bitcoin'
    '''

    final_home_url = home_url

    if url.startswith('/'):
        url = url[1:]

    try:
        if request is not None and request.META.get('HTTP_REFERER') is not None:
            # use the same protocol for the new url
            referer = request.META.get('HTTP_REFERER')
            if referer.find('://' + settings.TOP_LEVEL_DOMAIN) > 0 and referer.lower().startswith('https'):
                index = final_home_url.find('://')
                if index >= 0:
                    final_home_url = 'https' + final_home_url[index]
                    log(f'final url: {final_home_url}')
    except Exception:
        pass

    return urljoin(final_home_url, url)

def strip_input(data):
    '''Strip the leading and trailing spaces.

        >>> data = "  This is a line without end spaces.  "
        >>> strip_input(data)
        'This is a line without end spaces.'
    '''

    try:
        if data is not None:
            if is_string(data) or isinstance(data, CharField):
                data = data.strip()

            elif isinstance(data, EmailField):
                data = f'{data}'
                data = data.strip()

            elif isinstance(data, bytes):
                data = data.decode().strip()
    except Exception:
        log(format_exc())

    return data


if __name__ == "__main__":
    import doctest
    doctest.testmod()
