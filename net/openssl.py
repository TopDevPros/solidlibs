#!/usr/bin/env python3
'''
    Use openssl to generate a self-signed 4096 RSA cert.
    Requires solidlibs.net.cli, which requires pexpect to be installed from pypi.

    To do: Sanitize solidlibs.net.cli inputs.
    Do we need to include a "distinguished_name" or group or req name in the conf file?

    Copyright 2014-2023 solidlibs
    Last modified: 2023-05-17
'''

import os
import re
from datetime import datetime, timedelta
from subprocess import CalledProcessError
from traceback import format_exc

from solidlibs.os.cli import minimal_env, Responder
from solidlibs.os.command import run
from solidlibs.os.lock import locked
from solidlibs.python.log import Log

log = Log()

PRIVATE_KEY = 'private.key'
PUBLIC_CERT = 'public.crt'

# if openssl  is looking for openssl.cnf, it's in /etc/ssl
# openssl wants the path in the env var OPENSSL_CNF
OPENSSL_CONF_FILENAME = '/etc/ssl/openssl.cnf'

SELF_SIGNED_CERT_ERR_MSG = 'self signed certificate'
EXPIRED_CERT_ERR_MSG = 'certificate expired on'

def verify_certificate(hostname, port, ca_certs_dir=None):
    '''
        Verify a certificate is valid. Compare against openssl's published certs.

        Debian Jessie openssl does not support proxies, so we can't specify a
        tor proxy directly.

        >>> from solidlibs.os.user import whoami
        >>> if whoami() == 'root':
        ...     ok, __, __ = verify_certificate('google.com', 443)
        ...     ok
        ... else:
        ...     print(True)
        True

        >>> if whoami() == 'root':
        ...     ok, __, error_message = verify_certificate('SolidLibs.private.server', 443)
        ...     ok
        ...     error_message is None
        ... else:
        ...     print(False)
        ...     print(False)
        False
        False
    '''

    def extract_cert(response):

        cert = None

        i = response.find('-----BEGIN CERTIFICATE-----')
        if i > 0:
            temp_cert = response[i:]
            i = temp_cert.find('-----END CERTIFICATE-----')
            if i > 0:
                cert = temp_cert[:i+len('-----END CERTIFICATE-----')]

        return cert

    def verify_date(cert):

        ok = True
        error_message = None

        __, not_after = get_valid_dates(cert)
        try:
            after_date = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
        except:  # noqa
            try:
                after_date = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %z')
            except:  # noqa
                after_date = datetime.now() + timedelta(days=1)
        if after_date < datetime.now():
            ok = False
            error_message = f'{EXPIRED_CERT_ERR_MSG} {not_after}'

        return ok, error_message

    ok = True
    error_message = ''
    cert = None

    server = f'{hostname}:{port}'
    log(f'verify cert for {server}')

    if ca_certs_dir is None:
        ca_certs_dir = get_ca_certs_dir()
    log(f'ca certs dir: {ca_certs_dir}')

    try:
        # s_client waits for stdin after connecting, so we provide a short stdin
        # _in=' ' instead of _in='' because apparently sh does something like
        # checks '_in' instead of '_in is None'
        command_args = ['openssl', 's_client', '-connect', server, '-CApath', ca_certs_dir]
        result = run(*command_args)
        ##result = sh.openssl('s_client', '-connect', server, '-CApath', ca_certs_dir, _in=' ')

    except CalledProcessError as cpe:
        ##except sh.ErrorReturnCode as erc:
        ok = False
        try:
            stderr = cpe.stderr.strip()
            log(f'verify failed stderr:\n{stderr}')
            # parse 'connect: No route to host\nconnect:errno=22'
            # to 'connect: No route to host'
            error_message = stderr.split('\n')[0].strip()
        except:  # noqa
            error_message = cpe # 'Unable to verify SSL certificate'
        log(cpe)

    except:  # noqa
        log(format_exc())

    else:
        result_stderr = result.stderr
        log(f'verify result stderr:\n{result_stderr}')
        lines = result_stderr.split('\n')
        return_code = None
        for line in lines:
            if line.startswith('verify return:'):
                return_code = line[len('verify return:'):]
            elif line.startswith('verify error:'):
                m = re.match('verify error:num=(\d+):(.*)', line)
                if m:
                    return_code = m.group(1)
                    error_message += m.group(2)
                else:
                    return_code = -1
                    error_message = line

        # get the certificate so we can do additional verification
        cert = extract_cert(result.stdout)

        # it seems like we're never able to verify the local issuer so ignore the error
        if return_code == '0' and error_message == 'unable to get local issuer certificate':
            error_message = None

        if error_message is not None and len(error_message) > 0:
            ok = False
            log(f'error verifying {hostname} certificate: {error_message}')
        else:
            error_message = None

        if return_code == '0' and error_message is None:
            ok, error_message = verify_date(cert)

    log(f'{server} cert ok: {ok}')

    return ok, cert, error_message

def get_issuer(cert):
    '''
        Get the issuer of an SSL certificate.
    '''
    issuer = None
    try:
        ##result = sh.openssl('x509', '-noout', '-issuer', _in=cert)
        result = run('openssl', 'x509', '-noout', '-issuer', cert)
        result_stdout = result.stdout
        m = re.match('issuer=(.*)', result_stdout)
        if m:
            issuer = m.group(1).strip()
        else:
            log(f'issuer result stdout: {result_stdout}')
            log(f'issuer result stderr: {result.stderr}')
    except:  # noqa
        log(format_exc())

    return issuer

def get_issued_to(cert):
    '''
        Get to whom an SSL certificate was issued.
    '''
    issued_to = None
    try:
        result = run('openssl', 'x509', '-noout', '-subject', cert)
        result_stdout = result.stdout
        m = re.match('subject=(.*)', result_stdout)
        if m:
            issued_to = m.group(1).strip()
        else:
            log(f'issued_to result stdout: {result_stdout}')
            log(f'issued_to result stderr: {result.stderr}')
    except:  # noqa
        log(format_exc())

    return issued_to

def get_valid_dates(cert):
    '''
        Get the dates an SSL certificate is valid.
    '''
    not_before = not_after = None
    try:
        result = run('openssl', 'x509', '-noout', '-dates', cert)
        result_stdout = result.stdout
        m = re.match('notBefore=(.*?)\nnotAfter=(.*)', result_stdout)
        if m:
            not_before = m.group(1).strip()
            not_after = m.group(2).strip()
        else:
            log(f'dates result stdout: {result_stdout}')
            log(f'dates result stderr: {result.stderr}')
    except:  # noqa
        log(format_exc())

    return not_before, not_after

def get_hash(cert):
    '''
        Get the hash of an SSL certificate.
    '''
    cert_hash = None
    try:
        result = run('openssl', 'x509', '-noout', '-hash', cert)
        result_stdout = result.stdout
        cert_hash = result_stdout.strip()
    except:  # noqa
        log(format_exc())

    return cert_hash

def get_fingerprint(cert):
    '''
        Get the MD5 fingerprint of an SSL certificate.
    '''
    fingerprint = None
    try:
        result = run('openssl', 'x509', '-noout', '-fingerprint', cert)
        result_stdout = result.stdout
        m = re.match('SHA1 Fingerprint=(.*)', result_stdout)
        if m:
            fingerprint = m.group(1).strip()
        else:
            log(f'fingerprint result stdout: {result_stdout}')
            log(f'fingerprint result stderr: {result.stderr}')
    except:  # noqa
        log(format_exc())

    return fingerprint

def generate_certificate(
  domain, dirname, private_key_name=PRIVATE_KEY, public_cert_name=PUBLIC_CERT, name=None, days=365):
    '''
        Generate a self-signed SSL certficate.

        Writes the public cert to the file dirname/public_cert_name.
        Creates a dir dirname/private. Writes the private key to
        dirname/private/private_key_name.

        >>> generate_certificate('test.domain.com', '/tmp')
        >>> os.path.exists(os.path.join('/tmp', PUBLIC_CERT))
        True
        >>> os.path.exists(os.path.join('/tmp', 'private', PRIVATE_KEY))
        True
    '''

    if name is None:
        name = domain

    log(f'generate certificate for {name}')

    if not os.path.exists(dirname):
        os.makedirs(dirname)
        log(f'created {dirname}')

    private_dirname = os.path.join(dirname, 'private')
    if not os.path.exists(private_dirname):
        os.mkdir(private_dirname)
        log(f'created {private_dirname}')
    try:
        run('chown', 'root:ssl-cert', private_dirname)
    except:  # noqa
        try:
            run('chown', ':ssl-cert', private_dirname)
        except:  # noqa
            try:
                run('chown', 'root:root', private_dirname)
            except:  # noqa
                pass
    run('chmod', 'go-rwx', private_dirname)

    delete_old_cert(domain, dirname, private_key_name, public_cert_name)
    gen_private_key(domain, dirname, private_key_name)
    gen_csr(domain, dirname, name, private_key_name)
    gen_cert(domain, dirname, private_key_name, public_cert_name, days)
    log(f'created certificate for {domain}')

def gen_private_key(domain, dirname, private_key_name):
    '''
        Generate an openssl private key for the domain.

        >>> from shutil import rmtree
        >>> if os.path.exists('/tmp/private'):
        ...    rmtree('/tmp/private')
        >>> gen_private_key('test.domain.com', '/tmp', PRIVATE_KEY)
        >>> os.path.exists(os.path.join('/tmp', 'private', PRIVATE_KEY))
        True
    '''

    log('generate private key')

    private_dir = os.path.join(dirname, 'private')
    if not os.path.exists(private_dir):
        os.makedirs(private_dir)

    private_key = os.path.join(private_dir, private_key_name)
    temp_private_key = f'{private_key}.tmp'

    responses = [
        (f'Enter pass phrase for {private_key}:', 'secret'),
        (f'Verifying - Enter pass phrase for {private_key}:', 'secret'),
        ]

    args = ['genrsa', '-aes256', '-out', private_key, '4096']
    #args = ['genpkey', '-out', private_key, '-outform', 'PEM', '-aes256', '-algorithm', 'rsa', '-pkeyopt', 'rsa_keygen_bits:4096']
    log('responding to generating key')
    responder = Responder(responses, 'openssl', *args).run()
    log('finished responding to generating key')
    assert os.path.exists(private_key), f'could not generate {private_key}'

    log('copying private key to temp key')
    run('cp', private_key, temp_private_key)
    responses = [(f'Enter pass phrase for {temp_private_key}:', 'secret')]
    args = ['rsa', '-in', temp_private_key, '-out', private_key]
    log('answering openssl questions')
    responder = Responder(responses, 'openssl', *args).run()
    log(f'responder: {responder}')
    os.remove(temp_private_key)

def gen_csr(domain, dirname, name, private_key_name):
    ''' Generate an openssl CSR for the domain. '''

    log('generate csr')

    private_key = os.path.join(dirname, 'private', private_key_name)
    csr = os.path.join(dirname, f'{domain}.csr')

    responses = [
        ('Country Name \(2 letter code\) \[AU\]:', '.'),
        ('State or Province Name \(full name\) \[Some-State\]:', '.'),
        ('Locality Name \(eg, city\) \[\]:', '.'),
        ('Organization Name \(eg, company\) \[Internet Widgits Pty Ltd\]:', name),
        ('Organizational Unit Name \(eg, section\) \[\]:', '.'),
        ('Common Name \(e\.g\. server FQDN or YOUR name\) \[\]:', domain),
        ('Email Address \[\]:', '.'),
        ('A challenge password \[\]:', ''),
        ('An optional company name \[\]:', ''),
        ]

    args = ['req', '-new', '-key', private_key, '-out', csr]
    Responder(responses, 'openssl', *args).run()
    assert os.path.exists(csr), f'could not generate {csr}'

def gen_cert(domain, dirname, private_key_name, public_cert_name, days):
    ''' Generate the public certificate. '''

    log('generating certificate')

    private_key = os.path.join(dirname, 'private', private_key_name)
    public_cert = os.path.join(dirname, public_cert_name)
    csr = os.path.join(dirname, f'{domain}.csr')

    run('openssl', 'x509','-req', '-days', str(days), '-in', csr, '-signkey', private_key, '-out', public_cert)
    assert os.path.exists(public_cert), f'could not generate {public_cert}'
    os.remove(csr)

    # only the owner should be able to read the private key
    run('chmod', 'u+r', private_key)
    run('chmod', 'u-wx', private_key)
    run('chmod', 'go-rwx', private_key)

    # everyone can read the public certificate
    run('chmod', 'ugo+r', public_cert)
    run('chmod', 'ugo-wx', public_cert)

def delete_old_cert(domain, dirname, private_key_name, public_cert_name):
    log(f'deleting old certficate files for {domain}')

    private_key = os.path.join(dirname, 'private', private_key_name)
    if os.path.exists(private_key):
        os.remove(private_key)
    elif os.path.exists(os.path.join(dirname, private_key_name)):
        os.remove(os.path.join(dirname, private_key_name))

    public_cert = os.path.join(dirname, public_cert_name)
    if os.path.exists(public_cert):
        os.remove(public_cert)

    csr = os.path.join(dirname, f'{domain}.csr')
    if os.path.exists(csr):
        os.remove(csr)

def move_private_key(dirname, private_key_name):
    ''' Move the private key to the dirname.

        By default openssl puts private keys in a 'private' subdir. Some
        apps need them in a different dir, such as the dir where the pub
        keys are.
    '''

    private_dir = os.path.join(dirname, 'private')
    private_key_path = os.path.join(private_dir, private_key_name)
    new_private_key_path = os.path.join(dirname, private_key_name)

    with locked():
        run('mv', private_key_path, new_private_key_path)
        log(f'moved {private_key_path} to {new_private_key_path}')
        # remove openssl's 'private' dir when empty
        if not os.listdir(private_dir):
            run('rmdir', private_dir)
        log(f'removed {os.path.join(private_dir, private_key_name)}')

def get_ca_certs_dir():
    '''
        Get the directory where openssl keeps known certs.

        >>> certs = get_ca_certs_dir()
        >>> certs == '/etc/ssl/certs'
        True
    '''

    # /etc/ssl/certs is debian standard ca certs dir
    # alternatives include /usr/lib/ssl/certs, etc.
    ca_certs_dir = '/etc/ssl/certs'
    """
    try:
        result = run('openssl', 'version', '-d')
        result_stdout = result.stdout
        m = re.match('OPENSSLDIR: "(.*?)"', result_stdout)
        if m:
            ca_certs_dir = f'{m.group(1)}/certs'
    except:  # noqa
        log(format_exc())
    """

    return ca_certs_dir

def openssl_env():
    '''
        >>> env = openssl_env()
        >>> 'OPENSSL_CONF' in env
        True
    '''
    env = minimal_env()
    log(f'env: {env}')
    env['OPENSSL_CONF'] = OPENSSL_CONF_FILENAME
    log(f'env: {env}')

    return env

def sh_out(output):
    log.debug(output.rstrip())

def sh_err(output):
    log.warning(f'STDERR {output.rstrip()}')


if __name__ == "__main__":
    import doctest
    doctest.testmod()
