'''
    Context processor to set all custom template variables.

    Copyright 2009-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

try:
    from django.conf import settings
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

from solidlibs.net.browser import browser_types, is_primitive_browser
from solidlibs.python.log import Log

log = Log()


def custom(request):
    ''' Django context processor to set all custom template variables. '''

    custom_context = {}

    #DEBUG log(f'request: {request}')

    #custom_context.update(is_live(request))
    custom_context.update(debug(request))
    custom_context.update(browser(request))
    custom_context.update(css_ok(request))
    custom_context.update(javascript_ok(request))
    custom_context.update(is_active_user(request))

    return custom_context

def browser(request):
    ''' Django context processor to set 'browser' template variable.

        The 'browser' variable is a string containing common names of browsers
        compatible with the user's browser and platform. See
        http://web.koesbong.com/2011/01/28/python-css-browser-selector/

        Example

            <html class="{{ browser }}">
                ....
                {% if browser=='ie6' %}

                    ...

                {% endif %}
                ...

            </html>

        ---
    '''

    b = ' '.join(browser_types(request))
    #log('browser: %s' % b)
    return {'browser': b}

def css_ok(request):
    ''' Django context processor to set 'css_ok' template variable.

        The 'css_ok' variable is a boolean indicating if the user
        agent can properly display css.

        Example:

            {% if css_ok %}

                ...

            {% endif %}

    '''

    status = {'css_ok': not is_primitive_browser(request)}
    #log(f'css_ok: {status}')
    return status

def javascript_ok(request):
    ''' Django context processor to set 'javascript_ok' template variable.

        The 'javascript_ok' variable is a boolean indicating if the user agent
        can properly display javascript.

        Example

            {% if javascript_ok %}

                ...

            {% endif %}

        ---
    '''

    return {'javascript_ok': not is_primitive_browser(request)}


def is_live(request):
    ''' Django context processor to set 'is_live' template variable.

        The 'is_live' variable is a boolean indicating if the system is live.

        See debug()

        Example:

            {% if is_live %}

                ...

            {% endif %}

        '''
    try:
        live = settings.LIVE
    except Exception:
        live = False

    return {'is_live': live}


def debug(request):
    ''' Django context processor to set 'debug' template variable.

        The 'debug' variable is a boolean indicating if the system is in debug mode.

        The standard django.template.context_processors.debug sets 'debug',
        but only if:

        * in a RequestContext
        * settings.DEBUG is True
        * the request IP is in settings.INTERNAL_IPS

        This is too restrictive, especially the requirement for a RequestContext.

        Example:

            {% if debug %}

                ...

            {% endif %}

    '''

    return {'debug': settings.DEBUG}


def is_active_user(request):
    ''' Django context processor to set 'is_active_user' template variable.

        The 'debug' variable is a is_active_user indicating whether the use
        is authenticated and active.

        Example:

            {% if is_active_user %}

                ...


            {% endif %}

    '''

    try:
        active_user = {'is_active_user': request.user.is_authenticated and request.user.is_active}
    except Exception:
        active_user = {'is_active_user': False}

    return active_user
