#!/usr/bin/env python3
import argparse
import collections
import glob
import gzip
import hashlib
import json
import os
import pathlib
import pprint
import re
import shutil
import sqlite3
import subprocess
import tempfile
import urllib.request

import elftools.elf.elffile as elffile


def fetch():
    subprocess.run('./get-ubuntu-libcs.sh')
    subprocess.run('./get-debian-libcs.sh')
    subprocess.run('./get-arch-libcs.sh')


################################################################################


def identify(libc_filepath, show_matches=True):
    libc_buildID = extract_buildID_from_file(libc_filepath)
    try:
        if show_matches:
            print(json.dumps(libcs[libc_buildID], sort_keys=True, indent=4))
        return libcs[libc_buildID]
    except:
        pass


################################################################################


def extract_buildID_from_file(libc_filepath):
    output = subprocess.check_output('file {}'.format(libc_filepath), shell=True)
    output = output.strip().decode('ascii')
    buildID = re.search('BuildID\[sha1\]\=(.*?),', output).group(1)
    return buildID


def init_db():
    with sqlite3.connect('libcs.db') as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS libcs'
                     '(architecture text, distro text, release text, version text, buildID text, filepath text)')
        conn.execute('DELETE FROM libcs')


def create_db(libcs):
    init_db()

    with sqlite3.connect('libcs.db') as conn:
        for buildID in libcs:
            for libc in libcs[buildID]:
                conn.execute(
                    'INSERT INTO libcs VALUES (?, ?, ?, ?, ?, ?)',
                    (libc['architecture'], libc['distro'], libc['release'], libc['version'], buildID, libc['filepath']))


def parse_libcs():
    libcs = collections.defaultdict(list)
    for filepath in glob.glob('libcs/**/libc*.so', recursive=True):
        m = re.match(
            r'libcs/(?P<distro>.+?)/(?:(?P<release>.+?)/)?libc-(?P<architecture>i386|i686|amd64|x86_64)-(?P<version>.+?).so',
            filepath)

        buildID = extract_buildID_from_file(filepath)
        libcs[buildID].append({
            'distro': m.group('distro'),
            'architecture': m.group('architecture'),
            'release': m.group('release'),
            'filepath': filepath,
            'version': m.group('version')
        })

    return libcs


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


# check only the last 12 bits of the offset
def find(symbols_map):
    results = []
    # symbols_libc = {key:int(value) for key, value in (entry.split(' ') for entry in command_result.split('\n')) }

    for _, libc_entries in libcs.items():  # for each hash get the list of libcs
        for libc_entry in libc_entries:
            libc_path = f'./{libc_entry["filepath"]}'

            with open(libc_path, 'rb') as libc_file:
                elf = elffile.ELFFile(libc_file)
                dynsym_section = elf.get_section_by_name('.dynsym')

                for sym_name, sym_value in symbols_map.items():
                    try:
                        libc_sym = dynsym_section.get_symbol_by_name(sym_name)[0]
                        libc_sym_value = libc_sym.entry.st_value & int('1' * 12, 2)
                        if libc_sym_value != sym_value:
                            break
                    except TypeError | IndexError:
                        break
                else:
                    results.append(libc_entries)
    print(json.dumps(results, sort_keys=True, indent=4))


# arrive one string spliting the args with space
def symbol_entry(entry):
    symbol_name, addr_str = entry.split('=')
    addr = int(addr_str, 16) & int('1' * 12, 2)  # we take only the last 12 bits
    return {symbol_name: addr}


################################################################################

libcs = parse_libcs()
create_db(libcs)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')
    subparsers.required = True

    # action
    _ = subparsers.add_parser('fetch')
    identify_parser = subparsers.add_parser('identify')
    find_parser = subparsers.add_parser('find')

    # argument identify
    identify_parser.add_argument('libc', type=argparse.FileType())

    # find arguments
    find_parser.add_argument('symbols', type=symbol_entry, nargs='+', metavar='SYMBOL=OFFSET')

    args = parser.parse_args()

    if args.action == 'fetch':
        fetch()
    elif args.action == 'identify':
        identify(args.libc.name)
    elif args.action == 'find':
        symbols_map = dict(collections.ChainMap(*args.symbols))
        find(symbols_map)
