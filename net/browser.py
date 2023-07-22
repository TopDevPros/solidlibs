#!/usr/bin/env python3
'''
    Browser utilities.

    Copyright 2012-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import re
from traceback import format_exc

from solidlibs.python.log import Log

log = Log()

def user_agent_tags(ua):
    ''' Returns list of browser types indicated by the user agent.

        License: http://creativecommons.org/licenses/by/2.5/
        Credits:
            solidlibs: https://pypi.org/solidlibs
            This is a port from Koes Bong: http://web.koesbong.com/2011/01/28/python-css-browser-selector/,
            which is a port from Bastian Allgeier's PHP CSS Browser Selector: http://www.bastian-allgeier.de/css_browser_selector/,
            which is a port from Rafael Lima's original Javascript CSS Browser Selector: http://rafael.adm.br/css_browser_selector

    >>> user_agent_tags('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/536.5 (KHTML, like Gecko) Chrome/19.0.1084.56 Safari/536.5')
    ['webkit safari chrome', 'linux']
    >>> user_agent_tags('Safari/7534.57.2 CFNetwork/520.4.3 Darwin/11.4.0 (x86_64) (MacBookPro8%2C2)')
    ['unknown', 'mac']
    >>> user_agent_tags('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; .NET CLR 1.1.4322; .NET CLR 2.0.50727; .NET CLR 3.0.04506.30)')
    ['ie ie7', 'win']
    >>> user_agent_tags('Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.19) Gecko/2012020109 Iceweasel/3.0.6 (Debian-3.0.6-3)')
    ['gecko', 'linux']
    >>> user_agent_tags('curl/7.21.0 (i486-pc-linux-gnu) libcurl/7.21.0 OpenSSL/0.9.8o zlib/1.2.3.4 libidn/1.15 libssh2/1.2.6')
    ['curl', 'linux']
    >>> user_agent_tags('Lynx/2.8.8dev.5 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.8.6')
    ['lynx']
    >>> user_agent_tags('Wget/1.12 (linux-gnu)')
    ['wget', 'linux']

    '''

    browser = []

    try:
        ua = ua.lower()
        analyze_browser_type(ua, browser)
        analyze_platform(ua, browser)

    except:  # noqa
        browser.append('unknown')
        log(format_exc())

    return browser

def analyze_browser_type(ua, browser):
    '''
        Determine the browser type from the user agent.
    '''

    g = 'gecko'
    w = 'webkit'
    s = 'safari'

    opera_webtv_matches = re.search(r'opera|webtv', ua)
    opera_matches = re.search(r'opera(\s|\/)(\d+)', ua)
    msie_matches = re.search(r'msie\s(\d)', ua)

    if opera_webtv_matches is None and msie_matches is not None:
        browser.append('ie ie' + msie_matches.group(1))
    elif ua.find(r'firefox/2') != -1:
        browser.append(g + ' ff2')
    elif ua.find(r'firefox/4') != -1:
        browser.append(g + ' ff4')
    elif ua.find(r'firefox/3.6') != -1:
        browser.append(g + ' ff36')
    elif ua.find(r'firefox/3.5') != -1:
        browser.append(g + ' ff35')
    elif ua.find(r'firefox/3') != -1:
        browser.append(g + ' ff3')
    elif ua.find(r'firefox/5') != -1:
        browser.append(g + ' ff5')
    elif ua.find(r'gecko/') != -1:
        browser.append(g)
    elif opera_matches is not None:
        browser.append('opera opera' + opera_matches.group(2))
    elif ua.find(r'konquerer') != -1:
        browser.append('konquerer')
    elif ua.find(r'chrome') != -1:
        browser.append(w + ' ' + s + ' chrome')
    elif ua.find(r'iron') != -1:
        browser.append(w + ' ' + s + ' iron')
    elif ua.find(r'applewebkit/') != -1:
        applewebkit_ver_matches = re.search(r'version\/(\d+)', ua)
        if applewebkit_ver_matches is not None:
            browser.append(w + ' ' + s + ' ' + s + applewebkit_ver_matches.group(1))
        else:
            browser.append(w + ' ' + s)
    elif ua.find(r'mozilla/') != -1:
        browser.append(g)
    elif ua.find(r'chrome/') != -1:
        browser.append('chrome')
    elif ua.find(r'wget/') != -1:
        browser.append('wget')
    elif ua.find(r'lynx/') != -1:
        browser.append('lynx')
    elif ua.find(r'curl/') != -1:
        browser.append('curl')
    elif ua.find(r'unknown'):
        browser.append('unknown')

def analyze_platform(ua, browser):
    '''
        Determine the platform from the user agent.
    '''

    if ua.find('j2me') != -1:
        browser.append('j2me')
    elif ua.find('java') != -1:
        browser.append('java')
    elif ua.find('python') != -1:
        browser.append('python')
    elif ua.find('iphone') != -1:
        browser.append('iphone')
    elif ua.find('ipod') != -1:
        browser.append('ipod')
    elif ua.find('ipad') != -1:
        browser.append('ipad')
    elif ua.find('android') != -1:
        browser.append('android')
    elif ua.find('blackberry') != -1:
        browser.append('blackberry')
    elif ua.find('mobile') != -1:
        browser.append('mobile')
    elif ua.find('mac') != -1 or ua.find('darwin') != -1:
        browser.append('mac')
    elif ua.find('webtv') != -1:
        browser.append('webtv')
    elif ua.find('win') != -1:
        browser.append('win')
    elif ua.find('freebsd') != -1:
        browser.append('freebsd')
    elif ua.find('x11') != -1 or ua.find('linux') != -1:
        browser.append('linux')

def browser_types(request):
    ''' Returns list of compatible browser types from Django request. '''

    ua = request.META.get('HTTP_USER_AGENT', 'unknown')
    return user_agent_tags(ua)

def is_primitive_browser(request):
    ''' Returns whether browser is probably primitive.
        A browser is primitive if it can not properly display javascript or css. '''

    b = browser_types(request)
    dumb = (
        'unknown' in b or
        'wget' in b or
        'lynx' in b or
        'curl' in b or
        # presumably a modern browser written in a language will not identify as that language
        'python' in b or
        'java' in b)
    # log(f'is_primitive_browser: {dumb}')
    return dumb


def is_known_bot(browser, other):
    ''' Returns True if this access is from a known bot.

        >>> from solidlibs.net.web_log_parser import LogLine
        >>> line = '54.186.50.83 - - [21/Oct/2015:08:26:45 +0000] "GET /server/prices/ HTTP/1.1" 200 57201 "-" "BusinessBot: Nathan@lead-caddy.com"'
        >>> access = LogLine(line)
        >>> is_known_bot(access.browser_name, 'BusinessBot: Nathan@lead-caddy.com')
        True
        >>> is_known_bot(access.browser_name, access.other)
        True
        >>> is_known_bot('curl', 'agent: curl/7.26.0')
        True
        >>> b = '(compatible; Googlebot/2.1; +http://www.google.com/bot.html) agent: Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html'
        >>> is_known_bot('Mozilla', b)
        True
        >>> is_known_bot('ltx71', '(http://ltx71.com/)')
        True
        >>> is_known_bot('', '')
        False
        >>> line = '137.226.113.13 - - [25/Jan/2020:00:45:52 +0000] "GET / HTTP/1.1" 200 145465 "-" "Mozilla/5.0 zgrab/0.x"'
        >>> access = LogLine(line)
        >>> is_known_bot(access.browser_name, access.other)
        True
    '''

    try:
        browser_lc = browser.lower()
        other_lc = other.lower()

        known_bot = (
            ('mozilla' in browser_lc and len(other) <= 0) or # fake mozilla
            browser_lc.startswith('java') or # language lib
            'bot' in browser_lc or           # bot
            'bot' in other_lc or
            'spider' in browser_lc or        # spider
            'spider' in other_lc or
            'baiduspider' in browser_lc or   # BaiduSpider
            'baiduspider' in other_lc or
            'walker' in browser_lc or        # walker
            'walker' in other_lc or
            'crawl' in browser_lc or         # crawl
            'crawl' in other_lc or
            'python-urllib' in browser_lc or
            'libwww-perl' in browser_lc or
            'yahoo' in browser_lc or         # Yahoo
            'slurp' in browser_lc or         # slurp
            'slurp' in other_lc or
            'sleuth' in browser_lc or        # Xenu Link Sleuth
            'sleuth' in other_lc or          # Xenu Link Sleuth
            'curl' in browser_lc or          # curl
            'python' in browser_lc or        # python
            'perl' in browser_lc or          # perl
            'nambu' in browser_lc or         # nambu
            'docomo' in browser_lc or        # DoCoMo
            'digext' in browser_lc or        # DigExt
            'morfeus' in browser_lc or       # Morfeus
            'twitt' in browser_lc or         # twitt
            'sphere' in browser_lc or        # sphere
            'pear' in browser_lc or          # PEAR
            'wordpress' in browser_lc or     # wordpress
            'radian' in browser_lc or        # radian
            'eventbox' in browser_lc or      # eventbox
            'monitor' in browser_lc or       # monitor
            'mechanize' in browser_lc or     # mechanize
            'facebookexternal' in browser_lc or # facebookexternal
            'scoutjet' in other_lc or        # Scoutjet
            'scrapy' in browser_lc or        # Scrapy
            'scrapy' in other_lc or
            'yandex' in browser_lc or        # Yandex
            'yandex' in other_lc or
            'nerdybot' in browser_lc or      # NerdyBot
            'nerdybot' in other_lc or
            'archiver' in browser_lc or      # Archiver
            'archiver' in other_lc or
            'ia_archiver' in browser_lc or   # Alexa
            'ia_archiver' in other_lc or
            'qqdownload' in browser_lc or    # QQ
            'qqdownload' in other_lc or
            'ask jeeves' in browser_lc or    # Ask Jeeves
            'ask jeeves' in other_lc or
            'ltx71' in browser_lc or         # Scan internet for security research purposes
            'ltx71' in other_lc or
            'zgrab' in browser_lc or         # Conformance Testing by a student
            'zgrab' in other_lc or
            'nmap scripting engine' in browser_lc or  # Nmap Scripting Engine
            'nmap scripting engine' in other_lc
            )
    except:  # noqa
        known_bot = False
        log(format_exc())

    log(f'"{browser} {other}" known bot: {known_bot}')

    return known_bot

def is_known_harvester(user_agent):
    ''' Returns True if this access is from a known harvester.

        >>> is_known_harvester('Java/1.4.1_04')
        True
        >>> is_known_harvester('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET')
        True
        >>> is_known_harvester('')
        False
    '''

    if user_agent and user_agent.strip():
        known_harvester = (user_agent.startswith('Java/1.4') or
                           user_agent.startswith('Java/1.5') or
                           user_agent.startswith('Java/1.6.') or
                           user_agent.startswith('Java/1.7') or
                           user_agent.startswith('Java/1.8') or
                           user_agent.startswith('Mozilla/4.0 (compatible ; MSIE 6.0; Windows NT 5.1)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows 98)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 5.0; Windows NT; DigExt; DTS Agent') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1)') or
                           user_agent.startswith('Mozilla/4.0(compatible; MSIE 5.0; Windows 98; DigExt)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)') or
                           user_agent.startswith('MJ12bot/v1.0.8 (http://majestic12.co.uk/bot.php?+)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 5.01; Windows NT 5.0)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 1.1.4322)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.2; .NET CLR 1.1.4322)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 5.0; Windows NT; DigExt)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)') or
                           user_agent.startswith('Mozilla/5.0 (compatible; Googlebot/2.1; http://www.google.com/bot.html)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows 98) XX') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.0)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 1.1.4322; .NET CLR 2.0.50727)') or
                           user_agent.startswith('Mozilla/5.0 (Windows; U; Windows NT 6.1; en-us; rv:1.9.2.3) Gecko/20100401 YFF35 Firefox/3.6.3') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; en)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; .NET CLR 1.1.4322)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; .NET CLR 1') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET') or
                           user_agent.startswith('ISC Systems iRc Search 2.1') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; .NET CLR 1.1.4322; .NET CLR 2.0.50727; .NET CLR 3.0.04506.30; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729)') or
                           user_agent.startswith('Mozilla/3.0 (compatible)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 2.0.50727)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 1.1.4322; InfoPath.1)') or
                           user_agent.startswith('Mozilla/3.0 (compatible; Indy Library)') or
                           user_agent.startswith('Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.8.0.7) Gecko/20060909 Firefox/1.5.0.7') or
                           user_agent.startswith('Missigua Locator 1.9') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET)') or
                           user_agent.startswith('Wells Search II') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.0; .NET CLR 1.0.3705)') or
                           user_agent.startswith('Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US; rv:1.9.2.11) Gecko/20101012 Firefox/3.6.11 GTB7.1 ( .NET CLR 3.5.30729; .NET4.0E)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.2; MyIE2; .NET CLR 1.1.4322)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; .NET CLR 1.1.4322)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 5.0; Windows NT)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 1.0.3705;') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Win32)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0; SLCC1; .NET CLR 2.0.50727; Media Center PC 5.0; .NET CLR 3.0.04506)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; .NET CLR 2.0.50727)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; InfoPath.1)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; .NET CLR 1.1.4322; .NET CLR 2.0.50727)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; InfoPath.2)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 5.5; Windows NT 5.0)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0b; Windows NT 6.0)') or
                           user_agent.startswith('Opera/9.0 (Windows NT 5.1; U; en)') or
                           user_agent.startswith('Microsoft URL Control - 6.01.9782') or
                           user_agent.startswith('Microsoft URL Control - 6.00.8862') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0; Win32)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0; SLCC1; .NET CLR 2.0.50727; .NET CLR 3.0.04506)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE8.0; Windows NT 6.0) .NET CLR 2.0.50727)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; FunWebProducts)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 5.5; Windows NT 4.0)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0; SLCC1; .NET CLR 2.0.50727; Media Center PC 5.0; .NET CLR 3.0.04506; InfoPath.2)') or
                           user_agent.startswith('Mozilla/5.0 (Windows NT 5.1; U; en) Opera 8.01') or
                           user_agent.startswith('Opera/9.00 (Windows NT 5.1; U; en)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.2; Win64; AMD64)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.0; .NET CLR 1.0.3705; .NET CLR 1.1.4322)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; FREE; .NET CLR 1.1.4322)') or
                           user_agent.startswith('8484 Boston Project v 1.0') or
                           user_agent.startswith('Mozilla/5.0 (compatible; MegaIndex.ru/2.0; +https://www.megaindex.ru/?tab=linkAnalyze)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; .NET CLR 1.1.4322; .NET CLR 2.0.50727; .NET CLR 3.0.04506.30)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; MRA 4.3 (build 01218))') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; .NET CLR 1.0.3705)') or
                           user_agent.startswith('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.2; SV1; .NET CLR 1.1.4322; .NET CLR 2.0.50727)') or
                           user_agent.startswith('Scama host killer')
                          )
        log(f'{user_agent} known harvester: {known_harvester}')

    else:
        log.debug('no user agent')
        known_harvester = False

    return known_harvester


def is_known_spammer(referer):
    '''Return True if the referer is a known spammer. '''

    return (
        'semalt.com' in referer or
        'buttons-for-website.com' in referer or
        'buttons-for-your-website.com' in referer or
        'see-your-website-here.com' in referer or
        'makemoneyonline.com' in referer or
        'domainsigma' in referer or
        'darodar.com' in referer or
        'econom.co' in referer or
        'ilovevitaly.co' in referer or
        'best-seo-offer.com' in referer or
        'domini.cat' in referer or
        'savetubevideo.com' in referer or
        'kambasoft.com' in referer or
        'http://123.249.24' in referer
          )

def get_agent_info(agent):
    '''Get the browser name, version, and other data from the agent.

       If agent not defined, return empty strings.
    '''

    if agent:
        User_Agent_Format = re.compile(r"(?P<browser>.*?)/(?P<version>[0-9\.]*)\s*(?P<other>\(?.*\)?)")
        if not isinstance(agent, str):
            agent = agent.decode()
        m = User_Agent_Format.search(agent)
        if m:
            browser_name = m.group('browser')
            browser_version = m.group('version')
            other = m.group('other')
        else:
            browser_name = browser_version = ''
            other = agent
    else:
        browser_name = browser_version = other = ''

    return browser_name, browser_version, other

def get_browser_name(user_agent_tags):
    if user_agent_tags is None:
        browser_name = None
    else:
        browser_name = user_agent_tags[0]

    return browser_name


if __name__ == "__main__":
    import doctest
    doctest.testmod()
