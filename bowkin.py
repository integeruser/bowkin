#!/usr/bin/env python3
import argparse
import collections
import glob
import gzip
import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
import urllib.request


def show():
    print(json.dumps(libcs, sort_keys=True, indent=4))


################################################################################


def fetch():
    subprocess.run('./get-ubuntu-libcs.sh')
    subprocess.run('./get-debian-libcs.sh')
    subprocess.run('./get-arch-libcs.sh')


################################################################################


def identify(libc_filepath):
    libc_buildID = extract_buildID_from_file(libc_filepath)
    try:
        print(libcs[libc_buildID])
    except:
        pass


################################################################################


def extract_buildID_from_file(libc_filepath):
    output = subprocess.check_output('file {}'.format(libc_filepath), shell=True)
    output = output.strip().decode('ascii')
    buildID = re.search('BuildID\[sha1\]\=(.*?),', output).group(1)
    return buildID


def build_db():
    libcs = collections.defaultdict(list)
    for libc_filepath in glob.glob('libcs/**/*libc*.so', recursive=True):
        if pathlib.Path(libc_filepath).stem.startswith('ld'):
            continue

        m = re.match(r'libcs/(?P<distro>.+?)/(?:(?P<release>.+?)/)?(?P<filename>.+?)$', libc_filepath)
        libcs[extract_buildID_from_file(libc_filepath)].append({
            'distro': m.group('distro'),
            'release': m.group('release'),
            'filename': m.group('filename')
        })

    with open('libcs.json', 'w') as f:
        json.dump(libcs, f, sort_keys=True, indent=4)

    return libcs


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')
    subparsers.required = True

    _ = subparsers.add_parser('show')

    _ = subparsers.add_parser('fetch')

    identify_parser = subparsers.add_parser('identify')
    identify_parser.add_argument('libc', type=argparse.FileType())

    args = parser.parse_args()

    libcs = build_db()

    if args.action == 'show':
        show()
    elif args.action == 'fetch':
        fetch()
    elif args.action == 'identify':
        identify(args.libc.name)
