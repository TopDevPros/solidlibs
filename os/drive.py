#! /bin/env python3
'''
    Drive lib

    Copyright 2018-2023 solidlibs
    Last modified: 2023-05-17
'''

import sys
import time
from subprocess import CalledProcessError

from solidlibs.os.command import run

KB = 10 ** 3
MB = KB * 1000
GB = MB * 1000
TB = GB * 1000

KiB = 2 ** 10
MiB = 2 ** 20
GiB = 2 ** 30
TiB = 2 ** 40

def list_block_devices():
    ''' List block devices, i.e. drives and partitions

        >>> blocks = list_block_devices()

        Example output::
            NAME MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT
            sda    8:0    0 698.7G  0 disk
            sda1   8:1    0 694.8G  0 part /
            sda2   8:2    0     1K  0 part
            sda5   8:5    0   3.9G  0 part [SWAP]
            sdb    8:16   1 970.5M  0 disk
            sdb1   8:17   1   958M  0 part
            sr0   11:0    1  1024M  0 rom
    '''

    blocks = []
    lsblk_out = run('lsblk', '--list').stdout
    lines = lsblk_out.split('\n')
    for line in lines:
        if line.startswith('s'):
            name = line.split()[0]
            blocks.append(name)

    return blocks

def list_drives():
    ''' List drives

        >>> drives = list_drives()
    '''

    drives = []
    for name in list_block_devices():
        # partitions end in a nonzero digit
        # '0' not included because 'sr0' is a drive
        drives.append(name.rstrip('123456789'))

    return sorted(set(drives))

def size(drive):
    ''' Return drive size in bytes. '''

    drive = full_dev_name(drive)
    size_str = run('blockdev', '--getsize64', drive).stdout
    return int(size_str)

def full_dev_name(drive):
    ''' Return full device name. E.g. /dev/sda

        If drive already starts with /dev/, it is returned unchanged.
    '''

    if not drive.startswith('/dev/'):
        drive = '/dev/' + drive
    return drive

def physically_select_drive():
    ''' Interactively require user to plug in the selected drive.

        Return device name of selected drive.

        Don't ask for the drive device name
        Have them safely specify the drive by plugging it in when requested

        Because this is a security measure, exits program on error.
    '''

    def diff_drives(drives_before):
        drives_now = list_drives()
        # debug(f'drives: {drives_now}') # DEBUG
        new_drives = set(drives_now) - set(drives_before)
        # debug(f'new drives: {new_drives}') # DEBUG
        return new_drives

    def get_new_drives():
        wait = 10 # seconds
        print("Be sure which drive you want to select.")
        print('')

        print('If the drive you are selecting is mounted, unmount it.')
        print('If the drive you are selecting is plugged in, unplug it.')
        print('')
        input('When the drive you are selecting is unmounted and unplugged, then press Enter.')
        drives_before = list_drives()

        print('')
        input('Plug in the drive you are selecting, then press Enter again.')

        print('Wait for the system to recognize the drive . . .')
        new_drives = diff_drives(drives_before)
        while (not new_drives) and wait:
            time.sleep(1)
            wait = wait - 1
            new_drives = diff_drives(drives_before)

        return new_drives

    try:
        new_drives = get_new_drives()

        if len(new_drives) > 1:
            sys.exit(f'more than one new drive: {new_drives}')

        elif len(new_drives) == 0:
            sys.exit('no new drive')

    except KeyboardInterrupt:
        # don't show traceback
        sys.exit('')

    else:
        drive = new_drives.pop()

    return full_dev_name(drive)

def uuid(device):
    ''' Return UUID for device, or if none return None. '''

    device = full_dev_name(device)

    # skip e.g. /dev/sr0
    if device.startswith('/dev/sd'):
        result = run('blkid', '-s', 'UUID', '-o', 'value', device).stdout
    else:
        result = None

    return result

def set_uuid(device, uuid):
    ''' Set UUID for device. '''

    run('tune2fs', '-U', uuid, full_dev_name(device))

def make_uuid():
    ''' Return a new UUID. '''

    return run('uuidgen').stdout

def deduplicate_uuids():
    ''' Interactively set new uuids for duplicate uuid drives .

        Some disk copy utilities duplicate uuids. Linux doesn't like that.
    '''

    def get_uuids():
        uuids = {}
        for block_device in list_block_devices():
            u = uuid(block_device)
            if u:
                uuids[full_dev_name(block_device)] = u
        return uuids

    print('Make sure all drives that may have duplicate uuids are plugged in.')
    input('Then press Enter')
    print('Waiting for system to recognize all drives. . .')
    time.sleep(10)
    print('')

    uuids = get_uuids()
    #print(uuids) # DEBUG
    unique_uuids = sorted(set(uuids.values()))

    # while there are dups
    while sorted(uuids.values()) != unique_uuids:

        for unique_uuid in unique_uuids:
            # get drives that match this uuid
            matches = []
            for block_device, u in uuids.items():
                if u == unique_uuid:
                    matches.append(block_device)

            # if this uuid has dups
            if len(matches) > 1:
                dup_block_devices = matches

                print(f"Found duplicate uuids for {','.join(dup_block_devices)}")
                print('Follow these instructions to physically select a drive, and change its uuid.')

                drive_to_change = physically_select_drive()

                # verify drive
                # partitions end in a digit, but not drives
                # this isn't quite right if multiple partitions
                # on a drive have the same uuid
                dup_drives = []
                for dup in dup_block_devices:
                    drive = dup.rstrip('0123456789')
                    if drive not in dup_drives:
                        dup_drives.append(drive)
                dup_drives = sorted(dup_drives)
                # print(dup_drives) # DEBUG
                while drive_to_change not in dup_drives:
                    print('')
                    print('{} is not in the list of duplicates: {}'.
                          format(drive_to_change, ','.join(dup_drives)))
                    drive_to_change = physically_select_drive()

                # find the matching block device, which may be a partition
                selected_block_device = None
                for block in dup_block_devices:
                    if block.startswith(drive_to_change):
                        if selected_block_device is None:
                            selected_block_device = block
                        else:
                            sys.exit(f'more than one matching block device on {drive_to_change}')
                if selected_block_device is None:
                    sys.exit(f'no matching block device on {drive_to_change}')
                #print(selected_block_device) # DEBUG

                print('')
                yesno = input('Are you sure you want to change the uuid for {}? (y/n)'.
                              format(selected_block_device))
                if ('y') in yesno or ('Y') in yesno:
                    new_uuid = make_uuid()
                    try:
                        set_uuid(selected_block_device, new_uuid)
                    except CalledProcessError as cpe:
                        print(cpe.stdout)
                        print(cpe.stderr)
                    else:
                        print(f'Set uuid of {selected_block_device} to {new_uuid}')

        uuids = get_uuids()
        unique_uuids = sorted(set(uuids.values()))


if __name__ == "__main__":


    import doctest
    doctest.testmod()
