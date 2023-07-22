'''
    Extra HTTP functions.
    http_addons is named to avoid conflict with python's http pacakge.

    Copyright 2013-2023 solidlibs
    Last modified: 2023-05-17

    HTTP is a byte oriented protocol.
    In general, this module expects and return bytes.
    Param dicts are an exception. Param names and values are strings.

    As a convenience, in some cases string parameters will be automatically converted to bytes.

    (Implementaion of these type guidelines are a work in progress.)

    To do: Tests, such as for params_to_str() and params_to_bytes()

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import ssl
from http import HTTPStatus
from http.client import HTTPConnection, HTTPSConnection
from http.client import responses as client_responses
from traceback import format_exc
from urllib.parse import urlparse, urlsplit, urlunsplit

from solidlibs.python.log import Log
from solidlibs.python.format import to_bytes, to_string
from solidlibs.python.utils import gunzip
from solidlibs.net.openssl import verify_certificate, SELF_SIGNED_CERT_ERR_MSG, EXPIRED_CERT_ERR_MSG
from solidlibs.python.dict import CaseInsensitiveDict

log = Log()

HTTP_EOL = b'\r\n'
HTTP_SEPARATOR = HTTP_EOL + HTTP_EOL

# dict to look up HTTP status code by name
code = {}
# yes, prospector, this is an iterable
for hs in HTTPStatus:
    code[hs.name] = hs.value

ports = dict(
    http = 80,
    https = 443)

def TEST_get_response(url, proxy=None, cert_file=None):
    ''' Get an HttpResponse for the url '''

    if proxy:
        log.debug(f'get response from "{url}" using proxy "{proxy}"')
        # see python - Using SocksiPy with SSL - Stack Overflow
        #     http://stackoverflow.com/questions/16136916/using-socksipy-with-ssl

        if not cert_file:
            cert_file = '/etc/ssl/certs/ca-certificates.crt'

        proxy_parts = urlsplit(proxy)

        try:
            from socks import socksocket, PROXY_TYPE_SOCKS5   # pylint: disable=import-outside-toplevel
        except:  # noqa
            msg = 'Requires the debian module from python-socksipy'
            log.debug(msg)
            raise Exception(msg)

        s = socksocket()
        s.setproxy(PROXY_TYPE_SOCKS5, proxy_parts.hostname, port=proxy_parts.port)
        s.connect(('check.torproject.org', 443))
        ss = ssl.wrap_socket(s, cert_reqs=ssl.CERT_REQUIRED, ca_certs=cert_file)

        # print "Peer cert: ", ss.getpeercert()

        ss.write(f"""GET / HTTP/1.0\r\nHost: {proxy_parts.hostname}\r\n\r\n""")

        content = []
        while True:
            data = ss.read()
            if not data: break
            content.append(data)

        ss.close()
        result = "".join(content)

    else:
        log.debug(f'get response from {url}')

        url_parts = urlsplit(url)
        if url_parts.scheme == 'https':
            HTTPxConnection = HTTPSConnection
        elif url_parts.scheme == 'http':
            HTTPxConnection = HTTPConnection
            kwargs = {}
        else:
            raise ValueError(f'{url_parts.scheme} not supported')

        conn = HTTPxConnection(url_parts.hostname,
            url_parts.port or ports[url_parts.scheme],
            **kwargs)

        relative_url = urlunsplit(('', '',
                url_parts.path, url_parts.query, url_parts.fragment))
        conn.request('GET', relative_url)

        result = conn.getresponse()

    return result

def get_response(url, proxy=None, cert_file=None):
    '''
        Get an HttpResponse for the url.

        >>> response = get_response('https://toparb.com')
        >>> response.status == 200
        True
    '''

    kwargs = {}
    url_parts = urlsplit(url)
    if url_parts.scheme == 'https':
        HTTPxConnection = HTTPSConnection
        if cert_file is not None:
            kwargs = dict(cert_file=cert_file)
    elif url_parts.scheme == 'http':
        HTTPxConnection = HTTPConnection
    else:
        raise ValueError(f'{url_parts.scheme} not supported')

    if proxy is None:
        log.debug(f'get response from {url}')
        connection = HTTPxConnection(url_parts.hostname,
                                     url_parts.port or ports[url_parts.scheme],
                                     **kwargs)

    else:
        log.debug(f'get response from "{url}" using proxy "{proxy}"')
        # weirdly, http.client.HTTPConnection() gets the proxy, and set_tunnel() gets the destination domain
        proxy_parts = urlsplit(proxy)
        connection = HTTPxConnection(
            proxy_parts.hostname,
            proxy_parts.port,
            **kwargs)

        connection.set_tunnel(
            url_parts.hostname,
            url_parts.port or ports[url_parts.scheme])

    relative_url = urlunsplit(('', '',
            url_parts.path, url_parts.query, url_parts.fragment))
    connection.request('GET', relative_url)

    return connection.getresponse()

def check_response(url, why=None, proxy=None):
    '''
        Check that we got a status code of 200 and some data from the url.

        'url" is the internet address you want to go to.
        'why' is why we're checking.
        'proxy' is http proxy.

        Returns response.

        response.data is set to http data.

        >>> response = check_response('https://toparb.com')
        >>> response.status == 200
        True
    '''

    def err_msg(err):
        msg = (f'''{err}
        why: {why}
        testing url: {url}''')

        if proxy:
            msg = msg + (f'''
        proxy url: {proxy}
        ''')

        return msg

    if not why:
        why = 'check http response'

    log.debug(f'url: {url}')
    try:
        response = get_response(url, proxy=proxy)
    except:  # noqa
        print(err_msg('error in get_response()'))
        raise

    # check for OK response
    assert response.status == 200, err_msg(f'bad status: {response.status}')

    # check data exists
    response.data = response.read()
    assert len(response.data) > 0, err_msg('no data')

    return response

def parse_request(request):
    '''
        Parse raw http request data into prefix, params, and data.

        'request' must be a string or bytes.

        Returns:
        'prefix' is same type as 'request'.
        'params' is a dict with names and values as strings.
        'data' is same type as 'request', or None.
    '''

    if isinstance(request, str):
        request = to_bytes(request)
    if not isinstance(request, bytes):
        raise TypeError("'request' must be bytes")

    prefix, _, remainder = request.partition(HTTP_EOL)

    if HTTP_SEPARATOR in remainder:
        raw_params, _, content = remainder.partition(HTTP_SEPARATOR)
    else:
        raw_params = remainder
        content = None
    params = parse_params(raw_params.split(HTTP_EOL))

    return prefix, params, content

def parse_response(response):
    '''
        Parse raw http response data into (prefix, params, content).

        Returns:
        'prefix' and 'content' are byte sequences.
        'params' is a dict.
    '''

    if isinstance(response, str):
        response = to_bytes(response)
    if not isinstance(response, bytes):
        raise TypeError("'response' must be bytes")

    header, _, content = response.partition(HTTP_SEPARATOR)
    prefix, params = parse_header(header)
    params, content = uncompress_content(params, content)

    return prefix, params, content

def unparse_response(prefix, params, data):
    ''' Constructs an http response.

        This is essentially the reverse of parse_response().
    '''
    return (prefix + HTTP_EOL +
            params_to_bytes(params) + HTTP_SEPARATOR +
            to_bytes(data))

def parse_prefix(prefix):
    ''' Parse raw http prefix.

        Returns (http_method, local_url, http_protocol, http_version). '''

    assert isinstance(prefix, bytes), f'type(prefix) must be bytes, not {type(prefix)}'

    try:
        http_method, local_url, protocol_version = prefix.split(b' ')
    except ValueError:
        log(f'ValueError in prefix: "{prefix}"')
        raise

    try:
        http_protocol, http_version = protocol_version.split(b'/')
    except ValueError:
        log(f'ValueError in protocol_version: "{protocol_version}"')
        raise

    return http_method, local_url, http_protocol, http_version

def parse_header(header):
    ''' Parse raw http header into prefix line and a CaseInsensitiveDict. '''

    lines = header.split(HTTP_EOL)
    prefix = lines[0]
    params  = parse_params(lines[1:])

    return prefix, params

def parse_params(lines):
    ''' Parse raw http params.

        Returns a CaseInsensitiveDict. Case of keys is not significant.

        Both names and values are strings. See params_to_bytes() and params_to_str().
    '''

    params = CaseInsensitiveDict()
    for line in lines:
        line = to_string(line).strip()
        if line:
            name, _, value = line.partition(':')
            name = name.strip()
            if name:
                value = value.strip()
                params[name] = value

    return params

def uncompress_content(params, data):
    ''' If content is gzipped, unzip it and set new Content-Length. '''

    if is_text(params) and is_gzipped(params):

        data = gunzip(data)
        del params['Content-Encoding']
        params['Content-Length'] = str(len(data))

    return params, data

def unicode_content(params, data):
    ''' Return content as unicode. If params specify a charset, decode data from that charset. '''

    # see Python Unicode HowTo
    #     http://docs.python.org/2/howto/unicode.html
    #         "Software should only work with Unicode strings internally,
    #         converting to a particular encoding on output."

    if isinstance(data, (bytes, bytearray)):
        charset = content_encoding_charset(params)
        if charset is None:
            # log.debug('no charset in http params')
            unicode_data = to_string(data)
        else:
            try:
                unicode_data = data.decode(charset, 'replace')
            except:  # noqa
                log.debug(f'charset {charset} not supported; trying defaults')
                unicode_data = to_string(data)
            else:
                log.debug(f'decoded http content using charset {charset}')

    elif isinstance(data, str):
        # str is already unicode
        unicode_data = data

    else:
        msg = f'could not decode http content of type {type(data)}'
        log.debug(msg)
        try:
            log.debug(format_exc())
        finally:
            raise ValueError(msg)

    return unicode_data

def create_response(status, params=None, data=None):
    ''' Return raw http response.

        'status' is an integer. http lib defines status constants.

        'params' is an optional dict. 'data' is an optional string. '''

    if params is None:
        params = {}
    if data is None:
        data = b''

    prefix = b'HTTP/1.1 {} {}'.format(status, client_responses[status])
    params['Content-Length'] = len(data)
    response = prefix + HTTP_EOL + params_to_bytes(params) + HTTP_SEPARATOR + to_bytes(data)
    return response

def params_to_str(params):
    ''' Convert params dict to http protocol params string. '''

    lines = []
    for name in params:
        line = f'{camel_case(to_string(name))}: {to_string(params[name])}'
        lines.append(line)

    params_as_str = to_string(HTTP_EOL).join(lines)
    return params_as_str

def params_to_bytes(params):
    ''' Convert params dict to http protocol params byte sequence. '''

    return to_bytes(params_to_str(params))

def header(data):
    ''' Parse header from raw http data '''

    header_data, _, _ = data.partition(HTTP_SEPARATOR)
    return header_data

def is_content_type(params, prefix):
    ''' Return True if Content-Type sarts with prefix, else False. '''

    result = (
        'Content-Type' in params and
        params['Content-Type'].startswith(prefix))
    return result

def is_html(params):
    return is_content_type(params, 'text/html')

def is_text(params):
    ''' Return True if params indicate content is text, else False. '''

    return is_content_type(params, 'text/')

def is_app_data(params):
    ''' Return True if params indicate content is application data, else False. '''

    return is_content_type(params, 'application/')

def is_image(params):
    ''' Return True if params indicate content is image data, else False. '''

    return is_content_type(params, 'image/')

def content_encoding_charset(params):
    ''' Parse content-encoding charset from http response. '''

    charset = None
    if 'Content-Type' in params:
        content_type =  params['Content-Type']
        # content-type = text/html; charset=UTF-8
        for ct_param in content_type.split(';'):
            if charset is None:
                if '=' in ct_param:
                    name, value = ct_param.split('=')
                    name = name.strip()
                    if name == 'charset':
                        charset = value.strip()

    return charset

def is_gzipped(params):
    ''' Return True if params indicate content is gzipped, else False. '''

    return (
        'Content-Encoding' in params and
        'gzip' in params['Content-Encoding'])

def content_length(url):
    ''' Return content length of url.

        >>> # test including redir from http: to https:
        >>> length = content_length('https://toparb.com')
        >>> assert length > 0
    '''

    import requests    # pylint: disable=import-outside-toplevel

    head = requests.head(url, timeout=0.001)

    # handle redirs
    while head.status_code >= 300 and head.status_code < 400:
        url = head.headers['Location']
        head = requests.head(url, timeout=0.01)

    return int(head.headers['Content-Length'])

def verify_cert_locally(host, port):
    ''' Verify the site's certificate using openssl locally. '''

    log.warning('verify_cert_locally() bypasses any proxy such as Tor, so it may leak DNS info')

    # Verify the cert is ok before proceeding
    log.debug(f'verifying cert for: {host}:{port}')
    ok, original_cert, cert_error_details = verify_certificate(host, port)
    log.debug(f'{host}:{port} cert ok: {ok}')

    if not ok:
        log.debug(cert_error_details)

        # if the cert is self signed or expired, let the user decide what to do
        if SELF_SIGNED_CERT_ERR_MSG in cert_error_details:
            log.debug('cert is self.signed')
            ok = True
        elif EXPIRED_CERT_ERR_MSG in cert_error_details:
            log.debug('cert is expired')
            ok = True

    return ok, original_cert, cert_error_details

def camel_case(name):
    '''
        Upper case the first letter of each word in the name.

        >>> camel_case('how-to-verify-hash')
        'How-To-Verify-Hash'
    '''

    assert isinstance(name, str)
    return name.replace('-', ' ').title().replace(' ', '-')

def get_agent_referer(request=None, user_agent=None):
    ''' Get the user agent and referer.

        Must pass the request or user agent or both.
    '''

    # try to get the user agent from the request
    if user_agent is None and request is not None:
        try:
            if 'HTTP_USER_AGENT' in request.META:
                user_agent = request.META['HTTP_USER_AGENT']
        except:            # noqa
            pass

    if user_agent is not None:
        if request is None:
            referer = 'Unknown'
        else:
            referer = request.META.get('HTTP_REFERER', 'Unknown')
    else:
        referer = 'Unknown'

    return user_agent, referer

def url_to_host(url, port=False):
    ''' Return hostname for url.

        If 'port' is True, includes any non-standard port. The default
        is to ignore the port.

        Relative urls return None.
    '''

    if not url:
        raise ValueError('url required')

    host = None
    url_parts = urlparse(url)
    if port:
        if url_parts.port and url_parts.port not in (80, 443):
            host = f'{url_parts.netloc}:{url_parts.port}'

    if host is None:
        host = url_parts.netloc

    return host


if __name__ == "__main__":
    import doctest
    doctest.testmod()
