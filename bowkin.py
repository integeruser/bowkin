#!/usr/bin/env python3
import argparse
import glob
import gzip
import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
import urllib.request


def read_db():
    try:
        with open(db_filename) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def write_db():
    with open(db_filename, 'w') as f:
        json.dump(libcs, f, sort_keys=True, indent=4)


################################################################################


def extract_buildID_from_file(libc_filepath):
    output = subprocess.check_output('file {}'.format(libc_filepath), shell=True)
    output = output.strip().decode('ascii')
    buildID = re.search('BuildID\[sha1\]\=(.*?),', output).group(1)
    return buildID


def update():
    subprocess.run('./get-ubuntu-libcs.sh')
    subprocess.run('./get-debian-libcs.sh')
    subprocess.run('./get-arch-libcs.sh')

    for libc_filepath in glob.glob('libcs/**/libc6_*.so', recursive=True):
        m = re.match(r'libcs/(?P<distro>.*?)/(?P<release>.*?)/(?P<libc_version>.*?).so', libc_filepath)
        libc_version = m.group('libc_version')
        libc_buildID = extract_buildID_from_file(libc_filepath)
        libc_distro = '{}/{}'.format(m.group('distro'), m.group('release'))
        if libc_buildID not in libcs:
            libcs[libc_buildID] = {'distros': [libc_distro], 'version': libc_version}
        else:
            if libc_distro not in libcs[libc_buildID]['distros']:
                libcs[libc_buildID]['distros'].append(libc_distro)


################################################################################


def identify(libc_filepath):
    libc_buildID = extract_buildID_from_file(libc_filepath)
    if libc_buildID in libcs:
        print(libcs[libc_buildID])
    else:
        print('Not in database.')


################################################################################

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')
    subparsers.required = True
    update_parser = subparsers.add_parser('update')
    identify_parser = subparsers.add_parser('identify')
    identify_parser.add_argument('libc', type=argparse.FileType())
    args = parser.parse_args()

    db_filename = 'db.json'

    libcs = read_db()

    if args.action == 'update':
        update()
    elif args.action == 'identify':
        identify(args.libc.name)
