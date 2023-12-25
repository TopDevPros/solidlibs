'''
    Use tor.

    Copyright 2013-2023 TopDevPros
    Last modified: 2023-06-14

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

from contextlib import contextmanager
import requests
import socket

from solidlibs.python.log import Log
from solidlibs.net.utils import is_listening, require_socks, NetException

log = Log()

# these hosts and ports are site specific
TOR_HOST = '127.0.0.1'
TOR_PORT = 9350

@contextmanager
def torsockets(host=None, port=None):
    ''' Context manager to use tor for all python sockets.

        Warning: This uses knowledge of python-socks (aka socksipy) internals.

        >>> manager = torsockets('127.0.0.1', '80')
        >>> str(manager).startswith('<contextlib._GeneratorContextManager object')
        True
    '''

    """ Alternatives::
            https://stackoverflow.com/questions/1096379/how-to-make-urllib2-requests-through-tor-in-python
            https://pypi.org/project/pyTorify/
            https://gist.github.com/DusanMadar/8d11026b7ce0bce6a67f7dd87b999f6b
    """

    require_socks()
    import socks

    if host is None:
        host = TOR_HOST
    if port is None:
        port = TOR_PORT

    if not is_listening(host, port):
        raise NetException(f'no server listening at {host}:{port}')

    try:
        # log('tor is listening') # DEBUG
        # log('torsockets() socks.get_default_proxy()') # DEBUG
        old_default_proxy = socks.get_default_proxy()

        try:

            try:
                # log('torsockets() socks.set_default_proxy()') # DEBUG
                socks.set_default_proxy(socks.PROXY_TYPE_SOCKS5, host, port)
            except Exception as e:
                log(e)
                raise
            else:
                # log('torsockets() back from socks.set_default_proxy()') # DEBUG
                yield

        finally:
            # log('torsockets() finally') # DEBUG
            if old_default_proxy is None:
                # there doesn't seem to be a standard way to do this in 'socks' module
                #log('reset socks.socksocket.default_proxy = None')
                socks.socksocket.default_proxy = None
            else:
                #log(f'reset socks.set_default_proxy(*old_default_proxy={repr(old_default_proxy)})')
                socks.set_default_proxy(*old_default_proxy)

    # socksipy compatible fallback
    # needed on Debian 8
    except AttributeError as ae:
        log(ae)
        log('socksipy compatible fallback')
        old_defaultproxy = socks.get_default_proxy()
        old_create_connection = socks.socket.create_connection
        old_socksocket = socks.socket.socket

        torify(host, port)
        try:
            yield

        finally:
            log('after socksipy compatible fallback')
            # WARNING: because there is no socks.get_default_proxy(), this
            #          requires magic knowledge of socks module internals
            #          specifically that socks.get_default_proxy() sets
            #          socks._defaultproxy
            socks._defaultproxy = old_defaultproxy
            socks.socket.socket = old_socksocket
            socks.socket.create_connection = old_create_connection

def torify(host=None, port=None):
    '''
        Use tor for all python sockets.

        WARNING: Almost always, the torsockets() context manager is safer. Use it if you can.

        You must call torify() very early in your app, before importing
        any modules that may do network io.

        The host and port are for your tor proxy. They default to '127.0.0.1'
        and 9050.

        Requires the socks module from SocksiPy.

        Warnings:

            If you call ssl.wrap_socket() before socket.connect(), tor may be
            disabled.

            This function only torifies python ssl calls. If you use e.g. the
            sh module to connect, this function will not make your connection
            go through tor.

        See http://stackoverflow.com/questions/5148589/python-urllib-over-tor
    '''

    require_socks()
    import socks

    def create_connection(address, timeout=None, source_address=None):
        ''' Return a socksipy socket connected through tor. '''

        log(f'create_connection() to {address} through tor')
        sock = socks.socksocket()
        sock.connect(address)
        return sock

    if host is None:
        host = TOR_HOST
    if port is None:
        port = TOR_PORT

    if not is_listening(host, port):
        raise NetException(f'no server listening at {host}:{port}')

    socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, host, port)
    socket.socket = socks.socksocket
    socket.create_connection = create_connection
    log(f'socket.socket and socket.create_connection now go through tor proxy at {host}:{port}')

def get_content(url, headers=None, tor=False):
    ''' Get content of url.

        'headers' is requests headers.
        If 'tor', connect through tor.

        Exceptions are logs and reraised.

        Returns content of url, or None.

        >>> try:
        ...     content = get_content('https://topdevpros.com')
        ...     content is not None
        ... except requests.exceptions.ConnectionError as ce:
        ...     ce is not None
        True
    '''

    content = None
    try:
        # if tor is True and is listening, use it
        if tor and is_listening(TOR_HOST, TOR_PORT):
            log.debug('connecting through tor')
            with torsockets(port=TOR_PORT):
                content = requests.get(url, headers=headers).content
        else:
            log.debug('connecting directly without tor')
            # we want .content to get bytes, not a str
            # we need bytes to encode to the html's specified encoding
            content = requests.get(url, headers=headers).content

        if content:
            log.debug(f'content length: {len(content)}')

        else:
            log.warning(f'no content from {url}')

    except requests.exceptions.ConnectionError as ce:
        log.debug(str(ce))
        raise

    except Exception as e:
        log.debug(e)
        raise

    return content

def download_file(url, filename, headers=None, tor=False):
    ''' Download content of url into filename.

        'headers' is requests headers.
        If 'tor', connect through tor.

        Returns content of url, or None.
    '''

    try:
        content = get_content(url, headers=headers, tor=tor)
        if content:
            with open(filename, 'wb') as outfile:
                outfile.write(content)

    except Exception as e:
        log.debug(e)
        raise

    return content


if __name__ == "__main__":
    import doctest
    doctest.testmod()

