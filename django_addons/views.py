'''
    Views

    Copyright 2019-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import os.path

try:
    import django
    django.setup()

    from django.http import Http404, HttpResponse
    from django.conf import settings
    from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
    from django.shortcuts import render
    from django.template import RequestContext

except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

from solidlibs.python.log import Log

log = Log()


class ChangePassword(PasswordChangeView):
    ''' Change the password for regular user when logged in. '''
    # keep the following pass because when we strip comments, we need a line of code
    pass      # pylint: disable=unnecessary-pass

class ChangePasswordDone(PasswordChangeDoneView):
    ''' Change the password done for regular user when logged in. '''
    # keep the following pass because when we strip comments, we need a line of code
    pass       # pylint: disable=unnecessary-pass

def catch_all(request, url, context={}):
    ''' Handle urls not previously defined.

        Try to find a matching template file.

        Warning: Using this function in urls.py can mask earlier errors. (Why?)
                 If a page isn't working, try commenting out the line in urls.py.

        >>> from django.test import RequestFactory
        >>> factory = RequestFactory()
        >>> request = factory.get('https://127.0.0.1/')
        >>> catch_all(request, 'https://127.0.0.1/unknown')
        Traceback (most recent call last):
             ...
        django.http.response.Http404: https://127.0.0.1/unknown
    '''

    def search_template_dirs(url):
        template = None
        for template_dir in settings.TEMPLATE_DIRS:
            if not template:
                path = os.path.join(template_dir, url)

                template = search_for_template(path, template_dir, url)
                if not template:
                    template = search_again(path, url)

        return template

    url = url.rstrip('/')
    log(f'catch_all: unable to find {url} so making one last effort')

    template = search_template_dirs(url)
    if template is None:
        if url.endswith('index.html'):
            url = url.replace('index.html', 'home.html')
            template = search_template_dirs(url)
        elif url.endswith('index.htm'):
            url = url.replace('index.htm', 'home.html')
            template = search_template_dirs(url)

    for template_dir in settings.TEMPLATE_DIRS:
        if not template:
            path = os.path.join(template_dir, url)

            template = search_for_template(path, template_dir, url)
            if not template:
                template = search_again(path, url)

    if template:
        response = render(request,
                          template,
                          context=RequestContext(request, context).flatten())
    else:
        log.debug(f'raising 404 for {url}')
        raise Http404(url)

    return response

def search_for_template(path, template_dir, url):
    template = None

    if os.path.exists(path):
        if os.path.isdir(path):
            for home in ['home', 'index']:
                for ext in ['.html', '.htm']:
                    if not template:
                        basename = home + ext
                        path = os.path.join(template_dir, url, basename)
                        if os.path.exists(path):
                            template = os.path.join(url, basename)
        else:
            template = url

    return template

def search_again(path, url):
    template = None

    for ext in ['.html', '.htm']:
        if not template:
            if not path.endswith(ext):
                full_path = path + ext
                if os.path.exists(full_path):
                    template = url + ext

    return template

def empty_view(request, url):
    ''' Return an empty response, i.e. no html, for junk urls.

        Example: bootstrap.min.css.map[Learn More]


        >>> from django.test import RequestFactory
        >>> factory = RequestFactory()
        >>> request = factory.get('https://127.0.0.1')
        >>> empty_view(request, 'https://127.0.0.1/bootstrap.min.css.map[Learn More]')
        <HttpResponse status_code=200, "text/html; charset=utf-8">
    '''

    log.debug(f'return an empty response for url: {url} with {request} request')

    return HttpResponse('')
