'''
    Custom django template tags and filters

    Copyright 2010-2022 SolidLibs
    Last modified: 2022-12-11

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import urllib.request

try:
    from django.conf import settings
    import django.forms
    from django.template import Library, Node
    import django.templatetags.static
    import django.utils.html
    from django.utils.safestring import mark_safe
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

from solidlibs.django_addons.templatetags.data_img import data_img
from solidlibs.django_addons.templatetags.lookup import lookup
from solidlibs.django_addons.templatetags.var import do_variables
from solidlibs.django_addons.utils import get_absolute_url
from solidlibs.net.html_addons import strip_whitespace_in_html
from solidlibs.python.log import Log
from solidlibs.python.times import timedelta_to_human_readable

log = Log()

register = Library()

static_url_prefix = get_absolute_url(settings.STATIC_URL, settings.CONTENT_HOME_URL)

# register imported tags and filters that we want to include when we load 'custom'
# re-registering django.templatetags.static.static apparently works
register.simple_tag(django.templatetags.static.static)
register.filter('data_img', data_img)
register.filter('lookup', lookup)
register.tag('var', do_variables)


@register.simple_tag
def get_title(title):
    # this is a special case
    title = settings.TOP_LEVEL_DOMAIN.title()

    return title

@register.simple_tag
def transcode(url):

    '''
    Template tag to get the contents of a url.

    You can't transcode local urls because django is not re-entrant.
    Instead, in the view set a template variable with the local content.

    This code assumes a url starting with STATIC_URL is served from a different server,
    and so is ok.

    Example usage:

        {% transcode 'http://example.com' %}

    Returns:

        ... contents of http://example.com page ...

    '''

    def url_ok(url):
        ''' A url is ok if it is static or not on the local server '''

        return (
            url.startswith(static_url_prefix) or
            not url.startswith(settings.CONTENT_HOME_URL))

    url = url.strip()
    url = get_absolute_url(url, settings.CONTENT_HOME_URL)
    assert url_ok(url), ValueError('transcode can only include content from other servers')
    stream = urllib.request.urlopen(url)
    contents = stream.read()
    stream.close()

    return contents


class MinWhiteSpaceNode(Node):

    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        ''' Collect the strings from all nodes into a single string, and
            remove excess white space from the entire string.'''

        mintext = True

        return strip_whitespace_in_html(self.nodelist.render(context), mintext)

@register.tag
def minwhitespace(parser, token):
    '''
        Template tag to remove excess white space.

        The Django builtin tag "spaceless" removes whitespace between html tags.
        This tries to remove as much white space as possible without changing the
        appearance of the rendered html.

        Warning: removes repeated whitespace everywhere, such as in embedded
        javascript and between <pre> html tags.

        Example usage:

            {% minwhitespace %}
                <p>
                    <a href="foo/">Foo</a>

                    Bar

                </p>

            {% endminwhitespace %}

        Returns:

            <p><a href="foo/">Foo</a>Bar</p>

    '''
    nodelist = parser.parse(('endminwhitespace',))
    parser.delete_first_token()

    return MinWhiteSpaceNode(nodelist)


class StripWhitespaceNode(Node):

    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        ''' Collect the strings from all nodes into a single string, and
            remove leading and trailing white space from the entire string.'''

        return self.nodelist.render(context).strip()

@register.simple_tag
def stripwhitespace(parser, token):
    '''
    Template tag to remove leading and trailing white space.

    Example usage::

        {% stripwhitespace %}




            <p>
                <a href="foo/">Foo</a>
                Bar
            </p>



        {% endstripwhitespace %}

    Returns::
        <p>
            <a href="foo/">Foo</a>
            Bar
        </p>

    '''
    nodelist = parser.parse(('endstripwhitespace',))
    parser.delete_first_token()

    return StripWhitespaceNode(nodelist)

@register.filter
def strip(value):
    ''' Strip text filter. Uses string.strip(). '''
    return mark_safe(value.strip())

@register.filter
def timedelta_in_words(value):
    ''' Timedelta to human readable template filter.'''
    return mark_safe(timedelta_to_human_readable(value))

@register.simple_tag
def blankline():
    ''' Template tag for a bootstrap css blank row.

        Example usage:

            {% blankline %}

        Returns:

            <div class="block"> &nbsp; </div>
    '''

    #return mark_safe('<p> &nbsp; </p>')
    return mark_safe('<div class="container block"> &nbsp; </div>')

@register.simple_tag
def bullet():
    ''' Template tag for an inline bullet point separator.

        In HTML:
        char   description          unicode   html       html entity    utf-8

        ·      Middle Dot           U+00B7    &#183;     &middot;       C2 B7
        •      Bullet               U+2022    &#8226;    &bull;         E2 80 A2
‧       -      Hyphenation Point    U+2027    &#8321;                   E2 80 A7
        ∙      Bullet Operator      U+2219    &#8729;                   E2 88 99
        ●      Black Circle         U+25CF    &#9679;                   E2 97 8F
        ⬤      Black Large Circle   U+2B24    &#11044;

        In CSS:
            \00B7

        Example usage:

            {% bullet %}

        Returns:

            '&bull;'

    '''

    html = '&bull;'

    return mark_safe(html)

@register.simple_tag
def title(*args):
    ''' Title text.

        Usage::

            {% title "My title" %}

        Use 'title'/'endtitle' if there are django template variables in the text
        or the text is more than one line.
    '''

    if args:
        text = args[0]
        html = django.utils.html.format_html('<h1> <strong> {} </strong> </h1>', text)
    else:
        html = django.utils.html.format_html('<h1> <strong> ')
    return html

@register.simple_tag
def endtitle():
    ''' End variable or multiline title text.

        Usage::

            {% title %}
                My title
            {% endtitle %}
    '''

    return django.utils.html.format_html('</strong> </h1>')

@register.simple_tag
def subtitle(*args):
    ''' NYT style subtitle.

        Usage::

            {% subtitle "My subtitle" %}

        Use 'subtitle'/'endsubtitle' if there are django template variables in the text
        or the text is more than one line.
    '''

    if args:
        text = args[0]
        html = django.utils.html.format_html('<h4> <strong> {} </strong> </h4>', text)
    else:
        html = django.utils.html.format_html('<strong> <h4>')
    return html

@register.simple_tag
def endsubtitle():
    ''' End variable or multiline NYT style subtitle.

        Usage::

            {% subtitle %}
                My subtitle
            {% endsubtitle %}
    '''

    return django.utils.html.format_html(' </strong> </h4>')

@register.simple_tag
def link_button(href, label,
                target=None, tooltip=None,
                onclick=None, active=True,
                primary=False, btnblock=False):
    '''
        Link shown as a button with consistent style.

        This button can be used anywhere a link is allowed.

        If your label includes template variables or filters,
        use the start_link_button/end_link_button form.

        To reference the button in javascript, see button_name_id().

        Usage: {% link_button "My href" "My label" %}
    '''

    html = start_link_button(href, label,
                                   target=target, tooltip=tooltip,
                                   onclick=onclick, active=active,
                                   primary=primary, btnblock=btnblock)
    html = html + django.utils.html.format_html(label)
    html = html + end_link_button()

    return html

@register.simple_tag
def start_link_button(href,
                      label=None,
                      target=None, tooltip=None,
                      onclick=None, active=True,
                      primary=False, btnblock=False):
    '''
        Link shown as a button with consistent style.

        This button can be used anywhere a link is allowed.

        Usage:
            {% start_link_button "My href" "Invisible label" %}

                My visible label

            {% end_link_button %}

        There are actually 2 labels for this button.  The invisible label
        in the tag is used only to create id= and name=. The visible label
        between start_link_button and end_link_button is the one users see.
        This allows you to change the visible label without changing tests
        or javascript that reference the tag id or name.

        To reference the button in javascript, see button_name_id().

    '''

    if primary:
        button_type = 'btn-primary'
    else:
        button_type = 'btn-secondary'

    if active:
        active_class = ''
    else:
        active_class = ' disabled'

    # make the buttons fill the block; good when multiple buttons in table
    if btnblock:
        block = ' btn-block'
    else:
        block = ''

    name, id_tag = button_name_id(label)

    extra = ''
    if target:
        extra += f' target="{target}"'
    if tooltip:
        extra += f' title="{tooltip}"'
    if onclick:
        extra += f' onclick="{onclick}"'

    BaseFormat = '<a href="{}" name="{}" id="{}" class="btn {}{}{}" role="button" {}> <strong>'
    html = django.utils.html.format_html(BaseFormat.format(href, name, id_tag, button_type, active_class, block, extra))

    return html

@register.simple_tag
def end_link_button():
    ''' End variable or multiline NYT style subtitle.

        Usage::

            {% start_link_button %}
                My label
            {% endsubtitle %}
    '''

    return django.utils.html.format_html(' </strong> </a>')

@register.simple_tag
def form_button(value, tooltip=None, name=None, id_tag=None, onclick=None, primary=True, btnblock=False, btntype=None):
    '''
        Consistent button tag style.

        This button is used in a form.

        The element's name is "VALUE-button". The element's id is "VALUE-id".
        VALUE is the button text value capitalized.

        To reference the button in javascript, make the "label" all
        lower case and replace spaces with dashes. Use the result
        as the button's name by suffixing "-button" and its id by
        prefixing "id-".

        Usage: {% form_button "Value" %}
    '''

    BaseFormat = '<input type="{}" value="{}" name="{}" id="{}" alt="{}" class="btn {} font-weight-bold {}" role="button" {}/>'

    if name is None and id_tag is None:
        name, id_tag = button_name_id(value)
    elif name is None:
        name, __ = button_name_id(value)
    elif id_tag is None:
        __, id_tag = button_name_id(value)

    if not btntype:
        btntype = 'button'

    extra = ''
    if tooltip:
        extra += f' title="{tooltip}"'
    if onclick:
        extra += f' onclick="{onclick}"'

    if primary:
        button_type = 'btn-primary'
    else:
        button_type = 'btn-secondary'

    # make the buttons fill the block; good when multiple buttons in table
    if btnblock:
        block = ' btn-block'
    else:
        block = ''

    btn_html = BaseFormat.format(btntype, value, name, id_tag, value, button_type, block, extra)
    html = django.utils.html.format_html(btn_html)

    return html


@register.simple_tag
def submit_button(*args, **kwargs):
    '''
        Consistent submit button style.

        This button is used in a form to submit form data.

        See button() for parameters.

        Usage: {% submit_button "Value" %}
    '''

    return form_button(*args, btntype='submit', **kwargs)


@register.simple_tag
def reset_button(*args, **kwargs):
    '''
        Consistent reset button style.

        This button is used in a form to reset form data.

        See button() for parameters.

        Usage: {% submit_button "Value" %}
    '''

    return form_button(*args, btntype='reset', **kwargs)


@register.simple_tag
def card(*args):
    ''' Our standard version of the bootstrap card.

        Usage::

            {% card "My card" %}

        Use 'card'/'endcard' if there are django template variables in the content
        or the content is more than one line.
    '''

    START_CARD_HTML = '<div class="card"><div class="card-body border rounded" style="background-color:whitesmoke">'

    if args:
        content = args[0]
        html = django.utils.html.format_html('{} {} {}', START_CARD_HTML, content, endcard())
    else:
        html = django.utils.html.format_html(START_CARD_HTML)
    return html

@register.simple_tag
def endcard():
    ''' End variable or multiline card content.

        Usage::

            {% card %}
                My card
            {% endcard %}
    '''

    return django.utils.html.format_html('</div> </div>')

@register.simple_tag
def form_as_table(form):
    ''' Render form as table.

        Django version is junk.

        To do: allow for "{% trans 'Email' %}:" labels.
    '''

    html = '<table>'
    for field in form.visible_fields():

        html = html + '<tr>'

        html = html + '<th>'
        html = html + field.label + ':'
        html = html + '</th>'

        html = html + '<td>'
        html = html + str(field)
        if field.errors:
            html = html + ('<br/>' +
                           '<font color="red">' +
                           str(field.errors) +
                           '</font>' +
                           '<br/>')
        html = html + '</td>'

        html = html + '</tr>'

    html = html + '</table>'

    return django.utils.html.format_html(html)

@register.simple_tag
def form_as_narrow(form):
    ''' Render narrow form. '''

    html = ''
    for field in form.visible_fields():

        html = html + field.label + ':' + '<br/>'
        html = html + '&nbsp;&nbsp;&nbsp;&nbsp;' + str(field) + '<br/>'
        if field.errors:
            html = html + ('&nbsp;&nbsp;&nbsp;&nbsp;' +
                           '<font color="red">' +
                           str(field.errors) +
                           '</font>' +
                           '<br/>')

    return django.utils.html.format_html(html)

@register.filter
def get_item_by_key(dictionary, key):
    ''' Solution for when a dict key might have characters that
        django will misinterpret, such as '/'.
    '''

    value = dictionary.get(key)
    # log(f'get_item_by_key() dictionary={dictionary}, key={key}, value={value}')
    return value

def button_name_id(label):
    ''' Return button name and id.

        The name and id are derived from the button label.

        To reference the button in javascript:
            1. Get the basename.
                a. make the "label" all lower case
                b. replace spaces with dashes.

            2. name = basename + "-button"
            3. id = "id-" + basename
    '''

    base = label.replace(' ', '-').replace('.', '').replace(',', '').replace("'", '').replace("?", '').replace("<br/>", '-').replace('&nbsp;', '').lower()
    name = f'{base}-button'
    id_tag = f'{base}-id'

    return name, id_tag
