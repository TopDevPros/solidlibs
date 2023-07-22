'''
    Convert an image file to a data uri.

    Copyright 2012-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import base64
import os.path

try:
    from django.conf import settings
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

from solidlibs.python.log import Log

log = Log()
debugging = False

img_cache = {}

def data_image(filename, browser=None, mime_type=None):
    ''' Encode a file in base 64 as a data uri.

        Args:
            filename:  The filename can be relative to settings.STATIC_ROOT
                       or include the full path to the data file to encode.
            browser:   As defined in solidlibs.net.browser.
                       Optional.
            mime_type: The mime type used to create the data URI.
                       Optional.

        Returns:
            A data URI.
            If the data uri is too large for ie8, or the "browser" doesn't
            support URIS, or anything goes wrong, returns the filename.

        >>> CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
        >>> filename = os.path.join(CURRENT_DIR, 'static', 'images', 'Kebab_icon.png')
        >>> data = data_image(filename)
        >>> data.startswith('data:image/png;base64')
        True
        >>> filename = os.path.join(CURRENT_DIR, 'static', 'images', 'Kebab_icon.png')
        >>> imagename = data_image(filename, browser='opera')
        >>> filename == imagename
        True
    '''

    if browser:
        log_if_debugging(f'browser: {browser}')

    # data uris don't work well with all browsers
    # opera only supports images up to 4K so we just ignore them
    if browser and (
                    'unknown' in browser or
                    'ie5' in browser or
                    'ie6' in browser or
                    'ie7' in browser or
                    'opera' in browser or
                    'java' in browser):

        log_if_debugging(f'browser "{browser}" does not support data uri')
        if filename.startswith('/'):
            result = filename
        else:
            result = '/static/' + filename

    elif filename in img_cache:

        result = img_cache[filename]

    else:

        log_if_debugging(f'filename : {filename}')

        result = filename
        try:
            if not mime_type:
                basename = filename.split('/')[-1]
                data_type = basename.split('.')[-1].lower()
                if data_type == 'jpeg':
                    data_type = 'jpg'
                # until we handle other types
                if data_type not in ['png', 'jpg', 'gif']:
                    assert ValueError, "filename does not end in '.png', '.jpg', or '.gif', and no mime_type specified"
                mime_type = f'image/{data_type}'
                log_if_debugging(f'set mime_type to {mime_type}')

            # if there's no leading path, add one
            pathname = os.path.join(settings.STATIC_ROOT, filename)
            log_if_debugging(f'pathname = {pathname}')

            '''
                Only IE8 is officially to limited to 32K.
                Earlier versions of Internet Explorer don't support data uris,
                and later ones don't have this limit.
                See http://en.wikipedia.org/wiki/Data_URI_scheme.

                But other browsers (e.g. Firefox on linux) can bog down
                badly with large data uris.
            '''
            # the RFC 2397 says the max size is 2100, but most browsers
            #  that support data images support larger images
            max_size = 100 * 1024
            if browser:
                if ('ie8' in browser):
                    max_size = 32 * 1024
                elif ('ff5' in browser):
                    max_size = 20 * 1024

            log_if_debugging(f'os.path.getsize({pathname})')
            log_if_debugging(f'os.path.exists({pathname}) = {os.path.exists(pathname)}')
            if os.path.exists(pathname):
                log_if_debugging(f'os.path.getsize({pathname}) = {os.path.getsize(pathname)}')
                if os.path.getsize(pathname) < max_size:
                    log_if_debugging(f'file_to_data_uri({pathname}, {mime_type}')
                    result = file_to_data_uri(pathname, mime_type)
                    log_if_debugging(f'done file_to_data_uri({pathname}, {mime_type})')

                else:
                    #log_if_debugging('IE8 does not allow data uris larger than 32K{pathname})
                    log_if_debugging(f'No data uris larger than 32K: {pathname}')
                    result = pathname
            else:
                msg = f'missing datafile: {pathname}'
                log.warning(msg)
                result = ''

        except Exception as e:
            log.error(e)
            # like django template processing, fail quietly
            result = ''

        log_if_debugging(f'result: {result}')
        img_cache[filename] = result

    return result

def data_uri(data, mime_type, charset=None):
    '''
        Convert binary data to a data uri.

        Args:
            data:      The binary data of an image.
            mime_type: The mime type used to create the data URI.
            charset:   The character set used to create the data URI.
                       Optional.

        Returns:
            A data URI.

        >>> CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
        >>> filename = os.path.join(CURRENT_DIR, 'static', 'images', 'Kebab_icon.png')
        >>> f = open(filename, 'rb')
        >>> data = f.read()
        >>> uri = data_uri(data, 'image/png')
        >>> uri.startswith('data:image/png;base64')
        True
    '''

    data_string = base64.b64encode(data).decode('utf-8').replace('\n', '')
    if charset:
        uri = f'data:{charset};{mime_type};base64,{data_string}'
    else:
        uri = f'data:{mime_type};base64,{data_string}'

    log_if_debugging(f'uri: {uri}')

    return uri

def file_to_data_uri(filename, mime_type):
    '''
        Convert file to a data uri.

        Args:
            filename:  The full path of an image.
            mime_type: The mime type used to create the data URI.

        Returns:
            A data URI.

        >>> CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
        >>> filename = os.path.join(CURRENT_DIR, 'static', 'images', 'Kebab_icon.png')
        >>> datauri = file_to_data_uri(filename, 'image/png')
        >>> datauri.startswith('data:image/png;base64')
        True
    '''

    with open(filename, 'rb') as input_file:
        datauri = data_uri(input_file.read(), mime_type)

    return datauri

def log_if_debugging(message):
    ''' Log if debugging.

        Args:
            message:  The information to record if debugging is True.
    '''

    if debugging:
        log.debug(message)
