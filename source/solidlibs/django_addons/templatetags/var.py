'''
    Create variables within templates

    Last modified: 2020-11-19

    Variables are set at render time. They are not available earlier,
    such as when {% block %} is evaluated.

'''

try:
    from django import template
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

import json
import re

from solidlibs.python.log import Log

log = Log()

register = template.Library()


class VariablesNode(template.Node):

    '''
        From http://djangoclips.org/clips/829/:

        Here is a Django template tag that allows you to create complex
        variables specified in JSON format within a template.

        It enables you to do stuff like:

        {% var as person %}
        {
            "firstName": "John",
            "lastName": "Smith",
            "address": {
                "streetAddress": "21 2nd Street",
                "city": "New York",
                "state": "NY",
                "postalCode": 10021
            },
            "phoneNumbers": [
                "212 555-1234",
                "646 555-4567"
            ]
        }
        {% endvar %}

        <p>{{person.firstName}}, </br>
            {{person.address.postalCode}}, </br>
            {{person.phoneNumbers.1}}
        </p>

        This tag also enables me to do dynamic CSS using as follows:

        # urlpatters
        urlpatterns = [
            (r'^css/(?P<path>.*\\.css)$', 'get_css'),
        ]

        #views
        def get_css(request, path):
            return render(request, 'css/%s' % path, {},
                mimetype="text/css; charset=utf-8")

        # dynamic css within in /path/to/app/templates/css'
        {% load var %}
        {% var as col %}
        {
            "darkbg": "#999",
            "lightbg": "#666"
        }
        {% endvar %}

        {% var as dim %}
        {
            "thinmargin": "2em",
            "thickmargin": "10em"
        }
        {% endvar %}

        body {
            background: {{col.darkbg}};
            margin: {{dim.thinmargin}};
        }

    '''

    def __init__(self, nodelist, var_name):
        self.nodelist = nodelist
        self.var_name = var_name
        log.debug(f'var_name: {var_name}')

    def render(self, context):
        source = self.nodelist.render(context)
        if source.strip().startswith('{'):
            value = json.loads(source)
            #log.debug(f'value from json: {value}')
        else:
            value = source
            #log.debug(f'value from source: {value}')
        log.debug(f'value type: {type(value)}')
        context[self.var_name] = value
        return ''

@register.tag(name='var')
def do_variables(parser, token):
    try:
        tag_name, arg = token.contents.split(None, 1)
    except ValueError:
        msg = f'"{token.contents.split()[0]}" tag requires arguments'
        log.debug(msg)
        raise template.TemplateSyntaxError(msg)
    log.debug(f'arg: {arg}')
    m = re.search(r'as (\w+)', arg)
    if m:
        var_name, = m.groups()
        log.debug(f'var_name arg: {var_name}')
    else:
        msg = f'"{tag_name}" tag had invalid arguments'
        log.debug(msg)
        raise template.TemplateSyntaxError(msg)

    nodelist = parser.parse(('endvar',))
    parser.delete_first_token()
    return VariablesNode(nodelist, var_name)
