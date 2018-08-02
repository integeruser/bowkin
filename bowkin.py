#!/usr/bin/env python3
import argparse
import collections
import glob
import json
import os
import pprint
import re
import sqlite3
import subprocess
import sys

import elftools.elf.elffile


def fetch():
    try:
        subprocess.run('fetchers/fetch-ubuntu-libcs.sh')
        subprocess.run('fetchers/fetch-debian-libcs.sh')
        subprocess.run('fetchers/fetch-arch-libcs.sh')
    except KeyboardInterrupt:
        pass


################################################################################


def extract_buildID_from_file(libc_filepath):
    output = subprocess.check_output('file {}'.format(libc_filepath), shell=True)
    output = output.strip().decode('ascii')
    buildID = re.search('BuildID\[sha1\]\=(.*?),', output).group(1)
    return buildID


def identify(libc_filepath, show_matches=True):
    libc_buildID = extract_buildID_from_file(libc_filepath)
    try:
        if show_matches:
            print(json.dumps(libcs[libc_buildID], sort_keys=True, indent=4))
        return libcs[libc_buildID]
    except KeyError:
        pass


################################################################################


def read_db():
    init_db()
    build_db()

    libcs = collections.defaultdict(list)
    with sqlite3.connect('libcs.db') as conn:
        for architecture, distro, release, version, buildID, filepath in conn.execute('SELECT * FROM libcs'):
            libcs[buildID].append({
                'architecture': architecture,
                'distro': distro,
                'release': release,
                'version': version,
                'filepath': filepath
            })
    return libcs


def init_db():
    with sqlite3.connect('libcs.db') as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS libcs'
                     '(architecture text, distro text, release text, version text, buildID text, filepath text)')


def build_db():
    with sqlite3.connect('libcs.db') as conn:
        conn.execute('DELETE FROM libcs')

        for filepath in glob.glob('libcs/**/libc*.so', recursive=True):
            m = re.match(
                r'libcs/(?P<distro>.+?)/(?:(?P<release>.+?)/)?libc-(?P<architecture>i386|i686|amd64|x86_64|armel|armhf|arm64)-(?P<version>.+?).so',
                filepath)
            buildID = extract_buildID_from_file(filepath)
            conn.execute(
                'INSERT INTO libcs VALUES (?, ?, ?, ?, ?, ?)',
                (m.group('architecture'), m.group('distro'), m.group('release'), m.group('version'), buildID, filepath))


################################################################################


def show_matches(libcs_matches):
    print('Possible entry:')
    for index, entry in enumerate(libcs_matches):
        print(f'{index}) ', end='')
        pprint.pprint(entry)
    print('Exit with -1')


def get_entry(libcs_matches):
    if len(libcs_matches) == 1:
        return libcs_matches[0]

    while True:  # until input is not valid or user want to exit
        show_matches(libcs_matches)
        string_choice = input('Chose one entry: ')

        try:
            choice = int(string_choice)
            if choice == -1:
                exit(0)
            elif 0 <= choice < len(libcs_matches):
                return libcs_matches[choice]
        except ValueError:
            print("Not valid")
            continue


################################################################################


def symbol_address_pair(string):
    symbol, address = string.split('=')
    offset = int(address, 16) & 0b111111111111
    return (symbol, offset)


def find(symbols):
    results = []

    for _, libc_entries in libcs.items():  # for each hash get the list of libcs
        for libc_entry in libc_entries:
            libc_path = f'./{libc_entry["filepath"]}'

            with open(libc_path, 'rb') as libc_file:
                elf = elftools.elf.elffile.ELFFile(libc_file)
                dynsym_section = elf.get_section_by_name('.dynsym')

                for symbol, address in symbols:
                    try:
                        libc_sym = dynsym_section.get_symbol_by_name(symbol)[0]
                        libc_address = libc_sym.entry.st_value & 0b111111111111
                        if libc_address != address:
                            break
                    except (TypeError, IndexError):
                        break
                else:
                    results.append(libc_entries)
    print(json.dumps(results, sort_keys=True, indent=4))


os.chdir(sys.path[0])
libcs = read_db()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')
    subparsers.required = True

    fetch_parser = subparsers.add_parser('fetch')

    identify_parser = subparsers.add_parser('identify')
    identify_parser.add_argument('libc', type=argparse.FileType())

    find_parser = subparsers.add_parser('find')
    find_parser.add_argument('symbols', type=symbol_address_pair, nargs='+', metavar='symbol=address')

    args = parser.parse_args()

    if args.action == 'fetch':
        fetch()
    elif args.action == 'identify':
        identify(args.libc.name)
    elif args.action == 'find':
        find(args.symbols)
