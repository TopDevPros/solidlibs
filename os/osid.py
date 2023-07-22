'''
    OS identification.

    Copyright 2008-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

from platform import system

def get_os_name():
    '''
        Return the name of the OS in lower case.

        >>> get_os_name()
        'linux'
    '''

    return system().lower()

def is_windows():
    '''
        Return True if the underlying OS is any variant of Windows.

        >>> is_windows()
        False
    '''

    osname = get_os_name()
    return osname.startswith("win") or osname.startswith("microsoft windows")

def is_windows_vista():
    ''' Return True if the underlying OS is Windows Vista.

        >>> is_windows_vista()
        False
    '''
    winVista = False
    osname = get_os_name()
    if is_windows():
        winVista = osname.find("vista") > 0
    return winVista

def is_windows7():
    ''' Return True if the underlying OS is Windows 7.

        >>> is_windows7()
        False
    '''
    win7 = False
    osname = get_os_name()
    if is_windows():
        win7 = osname.find("7") > 0
    return win7

def is_windows8():
    ''' Return True if the underlying OS is Windows 8.

        >>> is_windows8()
        False
    '''
    win8 = False
    osname = get_os_name()
    if is_windows():
        win8 = osname.find("8") > 0
    return win8

def is_windows10():
    ''' Return True if the underlying OS is Windows 10.

        >>> is_windows10()
        False
    '''
    win10 = False
    osname = get_os_name()
    if is_windows():
        win10 = osname.find("10") > 0
    return win10

def is_windows_xp():
    ''' Return True if the underlying OS is Windows XP.

        >>> is_windows_xp()
        False
    '''
    winXP = False
    osname = get_os_name()
    if is_windows():
        #  sometimes XP falsely reports that its W2K
        if osname.find("xp") > 0 or osname.find("2000") > 0:
            winXP = True
    return winXP

def is_unix():
    ''' Return True if the underlying OS is any variant of unix.

        >>> is_unix()
        True
    '''
    osname = get_os_name()
    return osname.find("unix") >= 0 or is_linux() or is_aix() or is_hp_unix() or is_solaris() or is_mac_os_x()

def is_linux():
    ''' Return True if the underlying OS is Linux.

        >>> is_linux()
        True
    '''
    osname = get_os_name()
    return osname.find("linux") >= 0

def is_aix():
    ''' Return True if the underlying OS is IBM's AIX.

        >>> is_aix()
        False
    '''
    osname = get_os_name()
    return osname.find("aix") >= 0

def is_hp_unix():
    ''' Return True if the underlying OS is HP's unix.

        >>> is_hp_unix()
        False
    '''
    osname = get_os_name()
    return osname.find("hp-ux") >= 0 or osname.find("hpux") >= 0 or osname.find("irix") >= 0

def is_solaris():
    ''' Return True if the underlying OS is Solaris.

        >>> is_solaris()
        False
    '''
    osname = get_os_name()
    return osname.find("solaris") >= 0 or osname.find("sunos") >= 0

def is_mac_os_x():
    ''' Return True if the underlying OS is Mac OS X.

        >>> is_mac_os_x()
        False
    '''
    osname = get_os_name()
    return osname.find("mac os x") >= 0

def is_mac():
    ''' Return True if the underlying OS is any variant of Mac.

        >>> is_mac()
        False
    '''
    osname = get_os_name()
    return osname.find("mac os") >= 0 or osname.find("macos") >= 0
