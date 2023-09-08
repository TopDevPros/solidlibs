'''
    Convert an image file to a data uri.

    Copyright 2012-2020 SolidLibs
    Last modified: 2020-11-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

try:
    from django import template
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

import solidlibs.django_addons.data_image

register = template.Library()

@register.filter
def data_img(filename, browser=None):
    ''' Encode an image file in base 64 as a data uri.
        The filename is relative to settings.STATIC_URL/settings.STATIC_ROOT.

        If the data uri is too large or anything goes wrong,
        returns the static path to the image file.

        Example:

            <img alt="embedded image" src="{{ 'images/myimage.png'|data_img:browser }}"/>

    '''

    return solidlibs.django_addons.data_image.data_image(filename, browser=browser)
