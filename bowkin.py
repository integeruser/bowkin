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
import subprocess
import tempfile
import textwrap
import urllib.request
import elftools.elf.elffile as elffile

def show():
    print(json.dumps(libcs, sort_keys=True, indent=4))


################################################################################


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


def build_db():
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

    with open('libcs.json', 'w') as f:
        json.dump(libcs, f, sort_keys=True, indent=4)

    return libcs


################################################################################


def create_base_image(base, base_image_name):
    try:
        subprocess.check_output(f'docker inspect {base_image_name}', shell=True)
    except subprocess.CalledProcessError:
        subprocess.run(f'docker build -f {base.name} -t {base_image_name} {os.path.dirname(base.name)}', shell=True)


def create_specific_image(libcs_entry, base_image_name, specific_image_name):
    try:
        subprocess.check_output(f'docker inspect {specific_image_name}', shell=True)
    except subprocess.CalledProcessError:
        libc_path = libcs_entry['filepath']
        libc_basename = os.path.basename(libc_path)
        ld_path = f'{os.path.dirname(libc_path)}/ld-{libc_basename}'

        with tempfile.TemporaryDirectory() as tempdir:
            print(tempdir / pathlib.Path('Dockerfile'))
            with open(tempdir / pathlib.Path('Dockerfile'), 'wb') as f:
                f.write(
                    textwrap.dedent(f'''\
                        FROM {base_image_name}:latest
                        ADD {libc_basename} /library/{libc_basename}
                        COPY ld-{libc_basename} /library/ld-{libc_basename}
                        WORKDIR /home''').encode('ascii'))
                shutil.copy(libc_path, tempdir)
                shutil.copy(ld_path, tempdir)
            subprocess.run(f'docker build -t {specific_image_name} {tempdir}', shell=True)


# if the container is yet running we stop it and remove the container
# so every active session (at most one) will be stopped, in this way every time that we start pwnerize
# we can choose the shared library. no more than one terminal can have access to a specific container
def run_container(container_name, share):
    try:
        subprocess.check_output(f'docker container inspect {container_name}', shell=True)
        subprocess.check_output(f'docker stop {container_name} && docker rm {container_name}', shell=True)
    except subprocess.CalledProcessError:
        pass

    if share:
        subprocess.run(
            f'docker run --name {container_name} --volume {share}:/home/share -it {container_name}', shell=True)
    else:
        subprocess.run(f'docker run --name {container_name} -it {container_name}', shell=True)


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


def clean(base_image_name, distro_name, libc_basename, container_name):
    image_name = container_name

    try:  # remove container
        subprocess.check_output(f'docker container inspect {container_name}', shell=True)
        subprocess.check_output(f'docker stop {container_name} && docker rm {container_name}', shell=True)
        print(f'Container {container_name} has been removed')
    except subprocess.CalledProcessError:
        print(f'''
        The container related with the libc {libc_basename} of the
        distro {distro_name} using the base image {base_image_name} not exist
        ''')
    try:  # try remove image
        subprocess.check_output(f'docker image inspect {image_name}', shell=True)
        subprocess.check_output(f'docker rmi {image_name}', shell=True)
        print(f'Image {image_name} has been removed')
    except:
        print(f'''
        The image related with the libc {libc_basename} of the
        distro {distro_name} using the base image {base_image_name} not exist
        ''')


def pwnerize(args):
    libcs_matches = identify(args.libc.name, show_matches=False)
    if not libcs_matches:
        print('No match found')
        exit(1)
    libcs_entry = get_entry(libcs_matches)

    distro_name = libcs_entry["distro"]
    libc_basename = pathlib.Path(libcs_entry["filepath"]).stem

    base_image_name = f'pwnerize-{pathlib.Path(args.base.name).stem}'
    base_and_distro_name = f'{base_image_name}-{distro_name}'
    specific_image_name = f'{base_and_distro_name}-{libc_basename}'
    container_name = specific_image_name

    if args.pwnerize_action == 'run':
        create_base_image(args.base, base_image_name)
        create_specific_image(libcs_entry, base_image_name, specific_image_name)

        run_container(container_name, args.share)
    elif args.pwnerize_action == 'clean':
        clean(base_image_name, distro_name, libc_basename, container_name)

################################################################################ 

# check only the last 12 bits of the offset
def find(symbols_map): 
    results = [] 
    # symbols_libc = {key:int(value) for key, value in (entry.split(' ') for entry in command_result.split('\n')) } 
     
    for _, libc_entries in libcs.items(): # for each hash get the list of libcs 
        for libc_entry in libc_entries: 
            libc_path = f'./{libc_entry["filepath"]}'

            with open(libc_path, 'rb') as libc_file:
                elf = elffile.ELFFile(libc_file)
                dynsym_section = elf.get_section_by_name('.dynsym')

                for sym_name, sym_value in symbols_map.items():
                    try:
                        libc_sym = dynsym_section.get_symbol_by_name(sym_name)[0]
                        libc_sym_value = libc_sym.entry.st_value & int('1'*12, 2)
                        if libc_sym_value != sym_value:
                            break
                    except TypeError | IndexError:
                        break
                else:
                    results.append(libc_entries)
    print(json.dumps(results, sort_keys=True, indent=4))
 
# arrive one string spliting the args with space 
def symbol_entry(entry): 
    symbol_name, addr_str = entry.split(',') 
    addr = int(addr_str, 16) & int('1'*12, 2) # we take only the last 12 bits 
    return {symbol_name: addr} 
 
################################################################################


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')
    subparsers.required = True

    # action
    _ = subparsers.add_parser('show')
    _ = subparsers.add_parser('fetch')
    identify_parser = subparsers.add_parser('identify')
    pwnerize_sub_parser = subparsers.add_parser('pwnerize')
    find_parser = subparsers.add_parser('find') 

    # argument identify
    identify_parser.add_argument('libc', type=argparse.FileType())

    # creation sub_parser pwnerize
    pwnerize_sub_parser = pwnerize_sub_parser.add_subparsers(dest='pwnerize_action')
    pwnerize_stop = pwnerize_sub_parser.add_parser('clean')
    pwnerize_run = pwnerize_sub_parser.add_parser('run')
    pwnerize_sub_parser.required = True

    # common arguments of the sub_parser of pwnerize
    pwnerize_stop.add_argument('base', type=argparse.FileType())
    pwnerize_run.add_argument('base', type=argparse.FileType())

    pwnerize_stop.add_argument('libc', type=argparse.FileType())
    pwnerize_run.add_argument('libc', type=argparse.FileType())

    # pwnerize_run specific argument
    pwnerize_run.add_argument('--share')

    # find arguments
    find_parser.add_argument('symbols', type=symbol_entry, nargs='+', metavar='SYMBOL,OFFSET')

    args = parser.parse_args()

    libcs = build_db()

    if args.action == 'show':
        show()
    elif args.action == 'fetch':
        fetch()
    elif args.action == 'identify':
        identify(args.libc.name)
    elif args.action == 'pwnerize':
        pwnerize(args)
    elif args.action == 'find':
        symbols_map = dict(collections.ChainMap(*args.symbols))
        find(symbols_map)
