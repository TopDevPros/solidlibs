'''
    Template middleware.

    Copyright 2011-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

try:
    from django.conf import settings
    from django.utils.deprecation import MiddlewareMixin
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

from solidlibs.python.log import Log

log = Log()

def set_context(response, key, value):
    # is this necessary, or can we just e.g. "response.context_data['request'] = request"?
    try:
        # TemplateResponse
        context = response.context
    except AttributeError:
        # SimpleTemplateResponse
        context = response.context_data
    if context is None:
        context = {}

    if key not in context:
        context[key] = value

class RequestMiddleware(MiddlewareMixin):
    ''' Add the request to the template context. '''

    def process_template_response(self, request, response):

        set_context(response, 'request', request)
        return response

class SettingsMiddleware(MiddlewareMixin):
    ''' Add the settings to the template context. '''

    def process_template_response(self, request, response):

        set_context(response, 'settings', settings)
        return response
