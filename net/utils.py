'''
    Net utilities.

    Copyright 2014-2023 solidlibs
    Last modified: 2023-05-17

    There is some inconsistency in function naming.

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import asyncio
import json
import re
import socket
from traceback import format_exc
from contextlib import contextmanager
from ssl import SSLContext, PROTOCOL_TLS
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler, Request
from urllib.error import HTTPError, URLError

from solidlibs.os.command import run
from solidlibs.os.user import whoami, require_user
from solidlibs.python.log import Log
from solidlibs.python.utils import stacktrace

log = Log()

class NetException(Exception):
    pass

def hostname():
    ''' Return:
            This system's host name. Convenience function.

        >>> from_hostname = hostname()
        >>> from_uname = run('uname', '--nodename').stdout.strip()
        >>> assert from_hostname == from_uname, f'hostname(): {from_hostname}, uname: {from_uname}'
    '''

    return socket.gethostname()

def hostaddress(name=None):
    ''' Get the host ip address.

        Returns None if not found.
        Default is to return this host's ip.

        Because this function uses gethostbyname(), be sure you are not
        vulnerable to the GHOST attack.
        https://security-tracker.debian.org/tracker/CVE-2015-0235
    '''

    ip = None

    host = name or hostname()
    #log.debug(f'host: {host}')

    try:
        host_by_name = socket.gethostbyname(host)

    except socket.gaierror:
        log.debug(f'no address for hostname: {host}')

    else:
        #log.debug(f'host by name: {host_by_name}')

        if name:
            ip = host_by_name

        else:
            # socket.gethostbyname(hostname()) can be wrong depending on what is in /etc/hosts
            # but interface_from_ip() requires we are root, and we want to continue if possible
            if whoami() == 'root':
                interface = interface_from_ip(host_by_name)
                if interface and not interface == 'lo':
                    log.debug(f'setting ip to host by name: {host_by_name}')
                    ip = host_by_name
                else:
                    log.warning(f'socket.gethostbyname(hostname()) returned {host_by_name}, ' +
                        'but no interface has that address. Is /etc/hosts wrong?')

            else:
                # accept socket.gethostbyname() because we can't verify it
                ip = host_by_name

    if not ip:
        # use the first net device with an ip address, excluding 'lo'
        for interface in interfaces():
            if not ip:
                if interface != 'lo':
                    ip = device_address(interface)
                    log.debug(f'set ip to {ip} from first net device {interface}')

    if ip:
        log.debug(f'ip address: {ip}')
    else:
        msg = 'no ip address'
        log.debug(msg)
        raise NetException(msg)

    return ip

def host_in_domain(host, domain):
    ''' Returns:
            True if host is equal to or a subdomain of domain.
            Else returns False.

        >>> host_in_domain('www.example.com', 'example.com')
        True
        >>> host_in_domain('example.com', 'www.example.com')
        False
    '''

    if not host:
        raise ValueError('host required')
    if not domain:
        raise ValueError('domain required')

    is_match = False
    while host and not is_match:
        if host == domain:
            is_match = True
            # log(f'{original_host} is in domain {domain}')

        # remove leftmost subdomain from host
        __, __, host = host.partition('.')

    return is_match

def host_in_domain_list(host, domains):
    ''' Returns:
            True if host is equal to or a subdomain of any domain in domains.
            Else returns False.

        >>> host_in_domain_list('www.example.com', ['example.com', 'test.com'])
        True
        >>> host_in_domain_list('example.com', ['www.example.com', 'test.com'])
        False
    '''

    is_match = False
    for domain in domains:
        if not is_match:
            is_match = host_in_domain(host, domain)

    return is_match

def get_main_domain(full_domain):
    '''
        Get the last 2 parts of a domain.

        >>> get_main_domain('www.example.com')
        'example.com'
        >>> get_main_domain('example.com')
        'example.com'
    '''

    parts = full_domain.split('.')
    total_parts = len(parts)
    if total_parts > 2:
        domain = f'{parts[total_parts-2]}.{parts[total_parts-1]}'
    else:
        domain = full_domain

    return domain

def interfaces():
    ''' Get net interfaces.

        >>> if whoami() == 'root':
        ...     'lo' in interfaces()
        ... else:
        ...     print(True)
        True
    '''

    require_user('root')
    output = run(*['/sbin/ifconfig']).stdout

    return re.findall(r'^(\S+?):?\s', output, flags=re.MULTILINE)

def net_interface():
    ''' Get the first net device excluding 'lo'.
        This is normally the ethernet interface.

        Return None if none.

        >>> if whoami() == 'root':
        ...     net_interface() != None
        ... else:
        ...     print(True)
        True
    '''

    first = None
    for interface in interfaces():
        if not first:
            if interface != 'lo':
                first = interface
    return first

def device_address(device):
    ''' Get device ip address

        >>> if whoami() == 'root':
        ...     address = device_address('lo')
        ...     address == '127.0.0.1'
        ... else:
        ...     print(True)
        True
    '''

    require_user('root')

    ip = None
    output = run(*['/sbin/ifconfig', device]).stdout
    for line in output.split('\n'):
        if not ip:
            m = re.match(r'.*inet (addr:)?(\d+\.\d+\.\d+\.\d+)\s', line)
            if m:
                ip = str(m.group(2))

    log.debug(f'{device} ip: {ip}')

    return ip

def mac_address(device):
    '''
        Get device mac address

        >>> if whoami() == 'root':
        ...     mac_address('lo')
    '''

    require_user('root')
    mac = None
    output = run(*['/sbin/ifconfig', device]).stdout
    for line in output.split('\n'):
        if not mac:
            m = re.match(r'.* HWaddr +(..:..:..:..:..:..)', line)
            if m:
                mac = m.group(1)
                log.debug(f'mac: {mac}')

    return mac

def interface_from_ip(ip):
    ''' Find interface using ip address

        >>> if whoami() == 'root':
        ...     interface_from_ip('127.0.0.1')
        ... else:
        ...     print("'lo'")
        'lo'
    '''

    interface_found = None
    for interface in interfaces():
        if not interface_found:
            if ip == device_address(interface):
                interface_found = interface

    return interface_found

@contextmanager
def connect_to(host, port):
    ''' Context manager that returns TCP socket connected to the host and port.

        Closes socket on context exit.

        >>> manager = connect_to('127.0.0.1', '80')
        >>> str(manager).startswith('<contextlib._GeneratorContextManager object')
        True
    '''

    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        yield s
    finally:
        if s:
            s.shutdown(socket.SHUT_RDWR)
            s.close()

def is_listening(host, port):
    '''
        Returns True if a listener is open on host:port. Else returns False.

        Attempts to open a connection to host:port, and if successful
        immediately closes it. A timeout returns False.

        >>> is_listening('127.0.0.1', 80)
        True
    '''

    s = None
    try:
        # log('is_listening() socket.socket()') # DEBUG
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        # log('is_listening() s.close()') # DEBUG
        # called on exit from 'with': s.close()

    except Exception:
        listening = False

    else:
        listening = True

    finally:
        if s:
            s.shutdown(socket.SHUT_RD)
            s.close()

    # log.debug(f'listening on {port}: {listening}')

    return listening

def set_etc_hosts_address(hostname, ip):
    '''
        Set host address in /etc/hosts from device address.

    '''

    def read_file(path):
        with open(path) as file:
            contents = file.read()
        return contents

    def write_etc_hosts(text):
        assert text.strip()
        with open('/etc/hosts', 'w') as hosts_file:
            hosts_file.write(text)

    def edit_text():
        # write /etc/hosts

        hostname_found = False
        newlines = []
        for line in oldlines:

            parts = line.split()

            # if hostname is already in /etc/hosts
            if hostname in parts:
                parts[0] = ip
                hostname_found = True

            line = ' '.join(parts)
            log.debug(f'new line: {line}')
            newlines.append(line)

        # if hostname is not in /etc/hosts
        if not hostname_found:
            # append the ip and hostname
            line = f'{ip} {hostname}'
            newlines.append(line)

        newtext = '\n'.join(newlines).strip() + '\n'
        log.debug(f'new text:\n{newtext}')
        return newtext

    require_user('root')

    oldlines = read_file('/etc/hosts').strip().split('\n')
    log.debug('old /etc/hosts:')
    message = '\n'.join(oldlines)
    log.debug(message)

    newtext = edit_text()
    assert newtext
    write_etc_hosts(newtext)

    # check /etc/hosts
    assert read_file('/etc/hosts') == newtext

def require_socks():
    '''
        Require python-socks/socksipy socks module. If missing, tell where to get it (which wasn't obvious).

    '''

    try:
        import socks    # pylint: disable=import-outside-toplevel
        log(f'socks proxy type: {socks.PROXY_TYPE_HTTP}')
    except ImportError:
        pkg = 'python3-socks'
        msg = f'Requires the debian module from {pkg}, or socksipy from pypi. Called from:\n{stacktrace()}'
        log(msg)
        raise NetException(msg)

def send_api_request(url, params, proxy_dict=None, user_agent=None):
    '''
        Send a post to a url and get the response.

        >>> params = []
        >>> page = send_api_request('https://toparb.com', params)
        >>> page is not None
        True

        >>> page = send_api_request('https://toparb.com/api/', {'api_version': '1.0', 'actions': 'versions'})
        >>> page is not None
        True

        >>> params = []
        >>> page = send_api_request('https://toparb.com', params, proxy_dict={'https': '127.0.0.1:8398'})
        >>> page is not None
        True
    '''

    def strip_left(html, search_string):
        i = html.lower().find(search_string)
        if i >= 0:
            html = html[i+len(search_string):]

        return html

    def strip_right(html, search_string):
        i = html.lower().find(search_string)
        if i >= 0:
            html = html[:i]

        return html

    # get the referer if possible
    referer = None
    __, __, ipaddrlist = socket.gethostbyaddr(socket.getfqdn())
    for ip_address in ipaddrlist:
        if ip_address != '127.0.0.1':
            referer = ip_address
            log(f'send_api_request with referer: {referer}')
            break

    page = post_data(url, params, proxy_dict=proxy_dict, user_agent=user_agent, referer=referer)

    if page is None:
        body_html = ''
        log('page is empty')
    else:
        body_html = page.strip()
        body_html = body_html.lstrip()
        body_html = strip_left(body_html, b'<body>')
        body_html = strip_right(body_html, b'</body>')
        body_html = body_html.strip()
        body_html = body_html.lstrip()

    return body_html

def post_data(full_url, params, proxy_dict=None, user_agent=None, referer=None):
    '''
        Send a post to a url and return the data.

        Args:
            full_url: the url, including the scheme, that you want to receive
            params: any extra parameters to be included in the post's header
            proxy_dict: (optional) formatted as {TYPE_OF_PROXY, PROXY_ADDRESS}
                        for example: proxy_dict={'https': 'http://127.0.0.1:8398'}
            user_agent: (optional) User agent included in the post's header (e.g., Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/536.5 (KHTML, like Gecko) Chrome/19.0.1084.56 Safari/536.5)
            referer: (optional) Referer included in the post's header

        Returns:
            data from the post.

        >>> page = post_data('https://toparb.com', '')
        >>> page is not None
        True
    '''

    page = None
    try:
        try:
            # import late so the rest of module can run even if there's no CookieJar
            from http.cookiejar import CookieJar    # pylint: disable=import-outside-toplevel
            if proxy_dict is None:
                opener = build_opener(HTTPCookieProcessor(CookieJar()))
            else:
                proxy_handler = ProxyHandler(proxy_dict)
                opener = build_opener(proxy_handler, HTTPCookieProcessor(CookieJar()))
        except NameError or ImportError:
            msg = 'Requires http.cookiejar'
            log(msg)
            raise NetException(msg)

        if params is None or len(params) < 1:
            encoded_params = None
        else:
            encoded_params = urlencode(params).encode()
            log(f'encoded params: {encoded_params}') #DEBUG

        request = Request(full_url, encoded_params)
        if user_agent is not None:
            request.add_header('User-Agent', user_agent)
        if referer is not None:
            request.add_header('Referer', referer)

        handle = opener.open(request)
        page = handle.read()

    except HTTPError as http_error:
        page = None
        log(f'full_url: {full_url}')
        log(f'http error: {str(http_error)}')

    except URLError as url_error:
        page = None
        log(f'{url_error} to {full_url}')

    except:  # noqa
        page = None
        log(f'full_url: {full_url}')
        log(format_exc())

    return page

def get_page(full_url, proxy_dict=None):
    '''
        Get a page from the url.

        full_url: the url, including the scheme, that you want to receive
        proxy_dict: (optional) formatted as {TYPE_OF_PROXY, PROXY_ADDRESS}
                    for example: proxy_dict={'https': 'http://127.0.0.1:8398'}

        >>> page = get_page('https://toparb.com')
        >>> page is not None
        True
    '''

    page = None
    try:
        if proxy_dict is None:
            opener = build_opener()
        else:
            proxy_handler = ProxyHandler(proxy_dict)
            opener = build_opener(proxy_handler)

        request = Request(full_url)
        handle = opener.open(request)
        page = handle.read()

    except HTTPError as http_error:
        page = None
        log(f'full_url: {full_url}')
        log(f'http error: {str(http_error)}')

    except URLError as url_error:
        page = None
        log(f'{url_error} to {full_url}')

    except:  # noqa
        page = None
        log(f'full_url: {full_url}')
        log(format_exc())

    return page

def websocket_send(url, message, secure=True):
    ''' Send a websocket message.

        'url' is a websocket url string. 'message' is a dict including a 'type' field.
        If 'secure' is False, ssl is not verified. The default for 'secure' is True.
    '''

    ''' Async syntax is different for different python versions.
        This is for python 3.5.

        Apparently every thread needs its own asyncio event loop.
        Python only creates one automatically for the main thread.
        See
            https://stackoverflow.com/questions/25063403/python-running-autobahnpython-asyncio-websocket-server-in-a-separate-subproce
    '''

    async def send_json():

        #log.debug('send_json')
        try:
            if secure:
                async with websockets.connect(url) as websocket:
                    await websocket.send(msg_json)
            else:
                context = SSLContext(protocol=PROTOCOL_TLS)
                async with websockets.connect(url, ssl=context) as websocket:
                    await websocket.send(msg_json)

        except NameError as n:
            log.debug(f'{str(n)} in send_json')
            raise

        except Exception as e:
            log.debug(e)
            raise

        #log.debug('exit send_json')

    # import delayed until we need websockets
    # on debian install python3-websockets
    import websockets

    #from solidlibs.python.utils import randint
    #nonce = randint()
    #log.debug(f"websocket_send('{url}', '{message}') nonce {nonce}")

    if type(url) is not str:
        raise TypeError(f'websocket url must be a string, not {type(url)}')
    if type(message) is not dict:
        raise TypeError(f'websocket message must be a dict, not {type(message)}')
    if 'type' not in message:
        raise ValueError("'type' required in websocket message")

    try:
        msg_json = json.dumps(message)

        need_loop = False
        try:
            # assume we have a current event loop
            asyncio.get_event_loop().run_until_complete(send_json())

        except RuntimeError as re:
            if 'There is no current event loop in thread' in str(re):
                need_loop = True
            else:
                log.debug(e)

        if need_loop:
            #log.debug('set current event loop')
            """ Apparently every thread needs its own asyncio event loop.
                See https://stackoverflow.com/questions/25063403/python-running-autobahnpython-asyncio-websocket-server-in-a-separate-subproce
                It may be better to use::
                    websockets.connect(loop=...)
            """
            asyncio_event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(asyncio_event_loop)

            asyncio.get_event_loop().run_until_complete(send_json())

    except NameError as n:
        log.debug(f'{str(n)} in websocket_send')
        raise

    except Exception as e:
        log.debug(e)
        raise

    finally:
        #log.debug(f"exit websocket_send('{url}', '{message}') nonce {nonce}")
        pass

def _test_websocket_send(url, message, secure=True):
    ''' Send a websocket message.

        'url' is a websocket url string. 'message' is a dict including a 'type' field.
        If 'secure' is False, ssl is not verified. The default for 'secure' is True.
    '''

    ''' Async syntax is different for different python versions.
        This is for python 3.5.
    '''

    async def send_json():

        log.debug('send_json')
        try:
            if secure:
                async with websockets.connect(url) as websocket:
                    await websocket.send(msg_json)
            else:
                context = SSLContext(protocol=PROTOCOL_TLS)
                async with websockets.connect(url, ssl=context) as websocket:
                    await websocket.send(msg_json)

        except Exception as e:
            log.debug(e)

        log.debug('exit send_json')

    log.debug('websocket_send')

    # import delayed until we need websockets
    try:
        import websockets    # pylint: disable=import-outside-toplevel
    except ModuleNotFoundError:
        raise ModuleNotFoundError('websockets not installed; on debian install python3-websockets')
    from solidlibs.python.dict import dictify   # pylint: disable=import-outside-toplevel

    if type(url) is not str:
        raise TypeError(f'websocket url must be a string, not {type(url)}')
    if type(message) is not dict:
        raise TypeError(f'websocket message must be a dict, not {type(message)}')
    if 'type' not in message:
        raise ValueError("'type' required in websocket message")

    try:
        msg_json = json.dumps(dictify(message))
        websockets_run(send_json)

    except Exception as e:
        log.debug(e)

    finally:
        log.debug('exit websocket_send')

@contextmanager
def websocket_receive(function, host, port):
    ''' Context manager to receive websocket messages.

        NOT TESTED

        Example::
            # not a doctest because it is a server, and so runs forever
            # you can run this in a separate thread
            async def echo(websocket, path):
                async for message in websocket:
                    await websocket.send(message)
            websocket_receive(echo, 'localhost', 8888)

       See:
            https://pypi.python.org/pypi/websockets
    '''

    # import delayed until we need websockets
    try:
        import websockets       # pylint: disable=import-outside-toplevel
    except ModuleNotFoundError:
        raise ModuleNotFoundError('websockets not installed; on debian install python3-websockets')

    asyncio.get_event_loop().run_until_complete(
        websockets.serve(function, host, port))
    asyncio.get_event_loop().run_forever()

def websockets_run(function):
    ''' Run function in asyncio event loop.

        'function' is a function without parameters to be run by asyncio. Example::
            asyncio.get_event_loop().run_until_complete(function())
        Do not include '()'.

        Apparently every thread needs its own asyncio event loop.
        Python only creates one automatically for the main thread.
        See
            https://stackoverflow.com/questions/25063403/python-running-autobahnpython-asyncio-websocket-server-in-a-separate-subproce
        It may be better to use::
            websockets.connect(loop=...)
    '''

    try:
        need_loop = False

        try:
            asyncio.get_event_loop().run_until_complete(function())
        except RuntimeError as re:
            if 'There is no current event loop in thread' in str(re):
                need_loop = True
            else:
                log.debug(re)

        if need_loop:
            log.debug('no current event loop')
            # see note above about every thread needing its own asyncio event loop
            asyncio_event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(asyncio_event_loop)

            asyncio.get_event_loop().run_until_complete(function())

    except Exception as e:
        log.debug(e)

    finally:
        log.debug('exit websocket_send')

def statsd_send(name, value, mtype, server=None, port=None):
    ''' Send to statsd.

        'name' is the name of the stat.

        'value' is the value.

        'mtype' is the statsd metric type, such as 'c' for a counter.

        'server' and 'port' are the statsd server ip and port. The default is 127.0.0.1:8125.
        8125 is the standard statsd port.

        >>> statsd_send('foo', 3, 'c')
        >>> statsd_send('foo2', 3, 'c')
        >>> statsd_send('foo3', 452, 'g')
    '''

    STATS_D_STANDARD_PORT = 8125

    if server is None:
        server = '127.0.0.1'
    if port is None:
        port = STATS_D_STANDARD_PORT

    message = f'{name}:{value}|{mtype}'
    udp_send(message, server, port)

def udp_send(message, server, port):
    ''' Send a udp packet.

        'message' is the bytes to send. 'server' and 'port' are the destination.
    '''

    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
        sock.sendto(bytes(message, "utf-8"), (server, port))

    finally:
        if sock:
            sock.close()


if __name__ == "__main__":
    import doctest
    doctest.testmod()
