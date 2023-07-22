'''
    Extra html functions.
    html_addons is named to avoid conflict with python's html pacakge.

    Copyright 2013-2023 solidlibs
    Last modified: 2023-05-18

    Requires BeautifulSoup, html5lib, and lxml for proper pretty printing of HTML.

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import re
from html.parser import HTMLParser

from solidlibs.python.format import strip_html, to_bytes, to_string
from solidlibs.python.log import Log

log = Log()

class LinkParser(HTMLParser):
    ''' Generic link parser.

        After parsing, self.links is a list::
            [(label, url), ...]

        >>> html = '<a href=/first> One </a> <a href=/second> Two </a>'

        >>> parser = LinkParser()
        >>> parser.parse(html)

        >>> print(parser.links)
        [('One', '/first'), ('Two', '/second')]

        >>> # as dict, with dup link text removed
        >>> print(dict(parser.links))
        {'One': '/first', 'Two': '/second'}
    '''

    def __init__(self, *args, **kwargs):
        self.links = []

        self.tag = None
        self.url = None
        self.title = None
        self.data = None

        super().__init__(*args, **kwargs)

    def parse(self, html):
        if isinstance(html, bytes):
            html = to_string(html)

        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tag = tag
        if tag == 'a':
            attrs = dict(attrs)
            self.url = attrs.get('href')
            if 'aria-label' in attrs:
                self.title = attrs['aria-label']

    def handle_endtag(self, tag):
        if tag == 'a':
            if not self.title:
                if self.data:
                    self.title = self.data
                else:
                    self.title = 'no title'

            if self.title and self.url:
                self.links.append((self.title, self.url))

            self.url = None
            self.title = None
            self.data = None

    def handle_data(self, data):
        data = data.strip()
        if data:
            self.data = data

    @staticmethod
    def html_to_links(html):
        ''' Return links from url.

            >>> html = '<a href=/first> One </a> <a href=/second> Two </a>'
            >>> links = LinkParser.html_to_links(html)

            >>> print(links)
            [('One', '/first'), ('Two', '/second')]
        '''

        parser = LinkParser()
        parser.parse(html)

        return parser.links

def extract_text(html):
    ''' Extract plain text from html.

        Prefers BeautifulSoup 4, but falls back to ad hoc extraction.

        >>> from solidlibs.net.utils import get_page
        >>> page = get_page('https://toparb.com')
        >>> page is not None
        True
        >>> text = extract_text(page)
        >>> text != page
        True
        >>> len(text) > 0
        True
    '''

    try:
        from bs4 import BeautifulSoup   # pylint: disable=import-outside-toplevel

    except ImportError:
        # ad hoc
        #log.debug(f'html: {repr(html)}')
        text = re.sub(r'<.*?>', ' ', html.strip())
        #log.debug(f'text after re: {text}')
        text = text.replace('  ', ' ')
        # some html tags are still present; overlapping regex matches?
        # throw away anything after the first '<'
        text, _, _ = text.partition('<')
        #log.debug(f'final text: {text}')

    else:
        # BeautifulSoup
        # from http://stackoverflow.com/questions/1936466/beautifulsoup-grab-visible-webpage-text
        soup = BeautifulSoup(html, features='lxml')
        texts = soup.findAll(text=True)

        def visible(element):
            if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
                return False
            if re.match('<!--.*-->', str(element)):
                return False
            return True

        visible_texts = list(filter(visible, texts))

        text = '\n'.join(visible_texts)

    return text

def get_links(htmlpath, exclude=None):
    ''' Get links from an html file.

        Not well tested. See our "feeds" for examples of more reliable parsing.

        Returns a list. Each item is a list of [PATH, URL, SUMMARY].

        'htmlpath' is path of html file.

        'exclude' is string in href to exclude, without top level domain.
        Example: To exclude links to google, use "exclude='google'".

        Very ad hoc.
    '''

    # fallable importdelayed until needed
    try:
        from pyquery.pyquery import PyQuery   # pylint: disable=import-outside-toplevel

    except ModuleNotFoundError as exc:
        raise Exception('pyquery not installed') from exc

    else:

        results = []

        with open(htmlpath) as infile:

            html = PyQuery(to_bytes(infile.read()))
            anchor_tags = html.items('a')
            # log.debug(f'{len(list(anchor_tags))} links: {htmlpath}') # DEBUG
            for item in anchor_tags:
                href = item.attr('href')
                if href and href.startswith('http'):
                    if exclude and (exclude not in href):
                        results.append([htmlpath, href, item.text().strip()])
                        # log.debug(f'\t{href}') # DEBUG

        return results

def expose_hidden_tags(html):
    ''' Make spoofed tags explicit. '''

    # this may not work with some cases. Example:
    #     <description>&lt; . . . &gt;</description>
    # a possible workaround is to re-encode these cases of '<' and '>' after firewalling

    if isinstance(html, str):
        start_tag = '<'
        end_tag = '>'
        hidden_start_tag = '&lt;'
        hidden_end_tag = '&gt;'
    elif isinstance(html, bytes):
        start_tag = b'<'
        end_tag = b'>'
        hidden_start_tag = b'&lt;'
        hidden_end_tag = b'&gt;'
    else:
        raise ValueError('html must be a string or bytes')

    if hidden_start_tag in html:
        #log.warning(f'exposing {str(hidden_start_tag)} in html')
        html = html.replace(hidden_start_tag, start_tag)
    if hidden_end_tag in html:
        #log.warning(f'exposing {str(hidden_end_tag)} in html')
        html = html.replace(hidden_end_tag, end_tag)

    return html

def clean_xml(xml):
    ''' Return (more) valid xml. Html is xml, so clean_xml() also cleans html.

        BeautifulSoup has a rep for accepting bad xml.
        Then it can write good xml.
    '''

    try:
        from bs4 import BeautifulSoup   # pylint: disable=import-outside-toplevel
    except ImportError:
        log('BeautifulSoup not installed so xml cannot be cleaned.')
        raise
    else:
        try:
            soup = BeautifulSoup(xml, features='html5lib')
        except Exception:
            # "features='lxml'" is to silence a very noisy and useless
            # error message from BeautifulSoup
            soup = BeautifulSoup(xml, features='lxml')

        cleaned_xml = soup.prettify()

    return cleaned_xml

def clean_html(html):
    ''' Return (more) valid html.

        Convenience function for clean_xml(html).
    '''

    return clean_xml(html)

def remove_doctype(html):
    ''' Remove all occurrences of DOCTYPE from html/xml.

        Some invalid html/xml has more than one DOCTYPE.
        A simple approach is to remove them both.

        This appears to be unnecessary if we call clean_xml().
        BeautifulSoup removes the extra DOCTYPE.

        This function actually removes all DOCTYPE headers, which
        appears to be overkill.
    '''

    DOCTYPE = r'\<!\s*DOCTYPE.*?\>'
    return re.sub(DOCTYPE, '', html, flags=re.IGNORECASE)

def find_tags(elements, tags, matches=None):
    ''' Find all matching tags in xmltodict elements. '''

    DEBUG = True

    def debug(msg):
        if DEBUG:
            log(f'find_tags: {msg}')

    def find_matches(elements, tags, matches):
        ''' Elements can have keys that are dicts,
            so handle regular keys and the fancier ones. '''

        for key in elements:

            if isinstance(key, dict):
                matches = find_matches(key, tags, matches)
            else:
                debug(f'subkey: {key}') # DEBUG
                value = elements[key]

                if key in tags:
                    debug(f'subkey matches tag: {key}') # DEBUG
                    if isinstance(value, list):
                        for v in value:
                            matches.append(v)
                    else:
                        matches.append(value)

                else:
                    if isinstance(value, dict):
                        debug('recursing') # DEBUG
                        matches = matches + find_tags(value, tags, matches)
                        debug('back from recursion') # DEBUG

                        # xmltodict.unparse(value, pretty=True)
                        keys = []
                        for subkey in value:
                            keys.append(subkey)
                        if keys:
                            debug(f'subkeys for "{key}":\n{keys}')

                    elif isinstance(value, str):
                        debug(f'subkey value: "{value}"')

                    elif isinstance(value, list):
                        for item in value:
                            debug(f'recursing {item}') # DEBUG
                            matches = matches + find_tags(value, tags, matches)
                            debug('back from recursion') # DEBUG

                    else:
                        debug(f'subkey value type: {type(value)}')
                        debug(f'subkey value: {repr(value)}')

        return matches


    # if single tag, make it a sequence
    if isinstance(tags, str):
        tags = [tags]

    # lower case tags
    tags = [tag.lower() for tag in tags]

    debug(f'search {elements}') # DEBUG
    debug(f'find tags matching {tags}') # DEBUG

    # if this is the top of the find_tags() recursion chain
    if matches is None:
        matches = []
    else:
        debug(f'matches {matches}') # DEBUG

    matches = find_matches(elements, tags, matches)

    return matches

def count_tags(elements, tag):
    ''' Count matching tags in elements. '''

    return len(find_tags(elements, tag))

def pretty_element(element):
    ''' Intended to return pretty-printed html element.
        But because we're using pyquery, just returns html.
    '''

    return element.html()
    # return to_string(lxml.etree.tostring(element, pretty_print=True)).strip()

def decode_html_file(path):
    ''' Decode an html file using the correct encoding.

        Any special encoding should be in the http header.
        But the requests lib would have already handled that.
        Sometimes an html/xml file will specify its encoding in
        an xml comment at the top of the file. That's what we
        are trying to handle here.
    '''

    log(f'UnicodeDecodeError: {path}')

    log(f'reread as bytes: {path}')
    # and try to decode
    with open(path, 'rb') as infile:
        content = infile.read()

    log(f'look for xml encoding: {path}')
    encoding = get_xml_encoding(content)
    if encoding:
        try:
            content = content.decode(encoding)
        except Exception:
            # the declared encoding may be wrong
            # try the default utf-8
            # this i
            content = content.decode()

        # lxml won't accept bytes with an encoding declaration
        log(f'strip any xml declaration: {path}')
        if content.strip().startswith('<?'):
            _, separator, suffix = content.partition('?>')
            if separator:
                content = suffix

    else:
        log.warning(f'UnicodeDecodeError, but no encoding specified: {path}')
        # to_string() tries common encodings
        content = to_string(content)
        log('successfully decoded content')

    return content

def get_xml_encoding(content):
    '''
        Get character encoding from xml header.
    '''

    encoding = None
    if content.strip().startswith(b'<?'):
        prefix, separator, _ = content.partition(b'?>')
        if separator:
            xml_declaration = prefix + separator
            log.debug(f'xml_declaration: {xml_declaration}')

            match = re.search(rb'encoding\s*=\s*[\"\'](.+?)[\"\']',
                              xml_declaration,
                              flags=re.IGNORECASE)
            if match:
                encoding = match.group(1)
                # log.debug(f'{self.name} encoding: {encoding}')

    return encoding

def get_title(html):
    ''' Get title from html.

        Return title, or None if no title found.

        >>> html = """
        ...     <html lang="en">
        ...         <head>
        ...              <title>
        ...                  Test title
        ...              </title>
        ...
        ...              <meta charset="utf-8">
        ...              </meta>
        ...         </head>
        ...
        ...         <body>
        ...             just a test
        ...         </body>
        ...
        ...     </html>
        ... """

        >>> print(get_title(html))
        Test title
    '''

    class TitleParser(HTMLParser):
        ''' Parse title from html.

            After parsing, self.title is the title, or None if no title.
        '''

        def __init__(self, *args, **kwargs):
            self.title = None
            self.in_head = False
            self.in_title = False

            super().__init__(*args, **kwargs)

        def parse(self, html):
            if isinstance(html, bytes):
                html = to_string(html)

            self.feed(html)

        def handle_starttag(self, tag, attrs):
            if tag == 'head':
                self.in_head = True
            elif tag == 'title':
                self.in_title = True

        def handle_endtag(self, tag):
            if tag == 'head':
                self.in_head = False
            elif tag == 'title':
                self.in_title = False

        def handle_data(self, data):
            if self.in_head and self.in_title:
                data = to_string(data).strip()
                if data:
                    self.title = data

    title = None

    if is_html(html):
        parser = TitleParser()
        parser.parse(html)
        title = parser.title

    return title

def get_title_using_re(html):
    ''' DEPRECATED. Use get_title()

        Get title from html.

        Return title, or None if no title found.

        >>> html = """
        ...     <html lang="en">
        ...         <head>
        ...              <title>
        ...                  Test title
        ...              </title>
        ...
        ...              <meta charset="utf-8">
        ...              </meta>
        ...         </head>
        ...
        ...         <body>
        ...             just a test
        ...         </body>
        ...
        ...     </html>
        ... """

        >>> print(get_title_using_re(html))
        Test title
    '''

    PATTERN = re.compile(rb'''<\s* title .*?>
                                  (.*?)
                              <\s*/\s* title \s*>
                         ''',
                         re.VERBOSE | re.DOTALL | re.IGNORECASE)


    title = None

    if is_html(html):
        match = PATTERN.search(to_bytes(html))
        if match:
            title = to_string(match.group(1).strip())

    return title

def strip_whitespace_in_html(value, mintext=False):
    ''' Returns the given HTML with minimum white space.

        To also change white space sequences in text between tags
        to a single space, set mintext to True. This is dangerous
        with embedded javascript, <pre>, etc.

        >>> strip_whitespace_in_html(' <a>   <b> test test2 </b></a>')
        '<a><b> test test2 </b></a>'
    '''

    value = value.strip()
    # no spaces around tags
    value = re.sub(r'>[\s\n\t]+<', '><', value)
    if mintext:
        # other space sequences replaced by single space
        value = re.sub(r'\s+', ' ', value)

    return value

def strip_cdata(s):
    ''' Strip CDATA markup. '''

    # Example:
    #     <![CDATA[Text we want to extract]]>
    return re.sub(r'<\s*!\s*\[\s*CDATA\s*\[(.*?)\s*]\s*]>',
                  r'\1',
                  s,
                  flags=re.IGNORECASE)

def spellcheck(html, lang="en_US", personal_dict=None):
    ''' Spell check the html depends on the debian package: enchant.

        Args:
            html:           The html content to be checked.
            lang:           The language of the spell checker.
                            Optional.
            personal_dict:  A list of words not in the standard dictionary
                            that should be considered spelled correctly.
                            Optional.
        Returns:
            Misspelled word:    List of misspelled words or an empty list if none misspelled.
            Text checked:       The text checked with __FOUND_MISSPELLED_WORD__ replacing any
                                misspelled words which allows caller to handle any special
                                cases in the text.
        Requires:
            pyenchant from PyPi.

        >>> html = '<html><body> Here is a test with a mispelled word.</body></html>'
        >>> spellcheck(html)
        (['mispelled'], '   Here is a test with a __FOUND_MISSPELLED_WORD__ word.  ')
    '''

    try:
        # import late because it's only needed if spellchecking used
        from enchant.checker import SpellChecker   # pylint: disable=import-outside-toplevel
    except ImportError as ie:
        message = 'Requires debian\'s "enchant" package be installed to use spellcheck().'
        log(f'{message}\n{ie}')
        raise ImportError(message) from ie

    misspelled_words = []
    checker = SpellChecker(lang=lang, text=strip_html(html))
    for error in checker:
        misspelled_word = checker.word
        misspelled = misspelled_word not in misspelled_words
        if personal_dict:
            misspelled = (misspelled_word.lower() not in personal_dict) and misspelled
        if misspelled:
            misspelled_words.append(misspelled_word)
        error.replace_always('__FOUND_MISSPELLED_WORD__')

    return misspelled_words, checker.get_text()

def is_html(s):
    ''' Return True if likely html, else False.

        Looks for <html>.

        >>> is_html('text')
        False

        >>> is_html('<a>')
        False

        >>> is_html('<html>')
        True
    '''

    PATTERN = rb'< \s* html .*? >'

    s_is_html = False
    if re.search(PATTERN, to_bytes(s),
                 flags=(re.IGNORECASE | re.VERBOSE)):
        s_is_html = True

    return s_is_html

def is_xml(s):
    ''' Return True if likely xml, else False.

        >>> is_xml('text')
        False

        >>> is_xml('<a>')
        True

        >>> is_xml('<p>')
        True

        >>> is_xml('<a> <p>')
        True
    '''

    PATTERN = rb'< \s* \w+ .*? >'
    match = re.search(PATTERN, to_bytes(s),
                      flags=(re.IGNORECASE | re.VERBOSE))

    return match is not None


if __name__ == "__main__":
    import doctest
    doctest.testmod()
