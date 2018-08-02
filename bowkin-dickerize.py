#!/usr/bin/env python3
import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import bowkin


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
        libc_basename = os.path.basename(libc_path).replace('libc-', '')
        ld_path = f'{os.path.dirname(libc_path)}/ld-{libc_basename}'

        with tempfile.TemporaryDirectory() as tempdir:
            with open(tempdir / pathlib.Path('Dockerfile'), 'wb') as f:
                f.write((
                    f'FROM {base_image_name}:latest\n'
                    f'ADD libc-{libc_basename} /env/lib/x86_64-linux-gnu/libc.so.6\n'
                    f'ADD ld-{libc_basename} /env/lib64/ld-linux-x86-64.so.2\n'
                    # f'RUN mkdir -p /env/lib/x86_64-linux-gnu && ln -s /env/libc-{libc_basename} /env/lib/x86_64-linux-gnu/libc.so.6\n'
                    # f'RUN mkdir -p /env/lib64 && ln -s /env/ld-{libc_basename} /env/lib64/ld-linux-x86-64.so.2\n'
                    # f'RUN mkdir -p /env/lib/x86_64-linux-gnu && ln -s /env/libc-{libc_basename} /env/lib/x86_64-linux-gnu/libc.so.6\n'
                    # f'RUN mkdir -p /env/lib64 && ln -s /env/ld-{libc_basename} /env/lib64/ld-linux-x86-64.so.2\n'
                    f'RUN mkdir -p /env/home && echo "mount -r --rbind /home /env/home" >> ~/.bashrc\n'
                    f'RUN sed -i "s|gdbserver_args += \\[\'localhost:0\'\\]|gdbserver_args += \\[\'--wrapper\', \'chroot /env\', \'--\', \'localhost:0\'\\]|" "$(find / -path \"/usr/*/pwnlib/gdb.py\")"\n'
                    f'WORKDIR /home').encode('ascii'))
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
            f'docker run --privileged --cap-add=SYS_PTRACE --name {container_name} --volume {share}:/home/share -it {container_name}',
            shell=True)
    else:
        subprocess.run(
            f'docker run --privileged --cap-add=SYS_PTRACE --name {container_name} -it {container_name}', shell=True)


def clean(base_image_name, distro_name, libc_basename, container_name):
    image_name = container_name

    try:  # remove container
        subprocess.run(
            f'docker container inspect {container_name}',
            shell=True,
            check=True,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL)
        subprocess.check_output(f'docker stop {container_name} && docker rm {container_name}', shell=True)
        print(f'Container {container_name} has been removed')
    except subprocess.CalledProcessError:
        print((f'The container related with the libc {libc_basename} of the'
               f'distro {distro_name} using the base image {base_image_name} not exist'))

    try:  # try remove image
        subprocess.run(
            f'docker image inspect {image_name}',
            shell=True,
            check=True,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL)
        subprocess.check_output(f'docker rmi {image_name}', shell=True)
        print(f'Image {image_name} has been removed')
    except:
        print((f'The image related with the libc {libc_basename} of the distro'
               f'{distro_name} using the base image {base_image_name} not exist'))


os.chdir(sys.path[0])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices={'clean', 'run'})
    parser.add_argument('base', type=argparse.FileType())
    parser.add_argument('libc', type=argparse.FileType())
    parser.add_argument('--share')
    args = parser.parse_args()

    libcs_matches = bowkin.identify(args.libc.name, show_matches=False)
    if not libcs_matches:
        print('No match found')
        exit(1)
    libcs_entry = bowkin.get_entry(libcs_matches)

    distro_name = libcs_entry["distro"]
    libc_basename = pathlib.Path(libcs_entry["filepath"]).stem

    base_image_name = f'bowkin-{pathlib.Path(args.base.name).stem}'
    base_and_distro_name = f'{base_image_name}-{distro_name}'
    specific_image_name = f'{base_and_distro_name}-{libc_basename}'
    container_name = specific_image_name

    if args.action == 'run':
        create_base_image(args.base, base_image_name)
        create_specific_image(libcs_entry, base_image_name, specific_image_name)

        run_container(container_name, args.share)
    elif args.action == 'clean':
        clean(base_image_name, distro_name, libc_basename, container_name)
