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


def read_db():
    try:
        with open(db_filename) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def write_db():
    with open(db_filename, 'w') as f:
        json.dump(libcs, f, sort_keys=True, indent=4)


def rebuild_db():
    global libcs
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
    write_db()


def print_db():
    print(json.dumps(libcs, sort_keys=True, indent=4))


################################################################################


def extract_buildID_from_file(libc_filepath):
    output = subprocess.check_output('file {}'.format(libc_filepath), shell=True)
    output = output.strip().decode('ascii')
    buildID = re.search('BuildID\[sha1\]\=(.*?),', output).group(1)
    return buildID


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

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')
    subparsers.required = True

    db_parser = subparsers.add_parser('db')
    db_parser.add_argument('--rebuild', action='store_true')

    _ = subparsers.add_parser('fetch')

    identify_parser = subparsers.add_parser('identify')
    identify_parser.add_argument('libc', type=argparse.FileType())

    args = parser.parse_args()

    db_filename = 'libcs.json'
    libcs = read_db()

    if args.action == 'db':
        if args.rebuild:
            rebuild_db()
        print_db()
    elif args.action == 'fetch':
        fetch()
    elif args.action == 'identify':
        identify(args.libc.name)
