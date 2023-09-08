'''
    Lookup key in dict

    Usage:

        {{ dictionary|lookup:key }}

    From:
        https://code.djangoproject.com/ticket/12486
        http://push.cx/2007/django-template-tag-for-dictionary-access

    Last modified: 2020-10-01
'''

try:
    from django import template
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')


register = template.Library()

@register.filter
def lookup(d, key):
    ''' Fix for django's lack of variable dict access in templates.

        Usage: {{ dictionary|lookup:key }}

        In a template, "{{ mydict.value }}" means "mydict['value']"
        instead of "mydict[value]".

        Use "{% for key, value in mydict.iteritems %}" when you can. But
        sometimes you can't, such as when you want dict access in a specific
        order.
    '''

    return d[key]
