#!/usr/bin/env python3
import argparse
import os
import re
import shlex
import shutil
import subprocess
import tempfile

import colorama

import bowkin


def extract_ld_and_libc(package_filepath, match):
    with tempfile.TemporaryDirectory() as tmp_dirpath:
        shutil.copy2(package_filepath, tmp_dirpath)

        package_filename = os.path.basename(package_filepath)
        subprocess.run(
            f"tar xf {shlex.quote(package_filename)}",
            cwd=tmp_dirpath,
            shell=True,
            check=True,
        )
        subprocess.run(
            f"if [ -f data.tar.xz ]; then tar xf data.tar.xz; fi",
            cwd=tmp_dirpath,
            shell=True,
            check=True,
        )

        libc_filepath = (
            subprocess.run(
                f"realpath $(find . -name 'libc.so.6')",
                cwd=tmp_dirpath,
                shell=True,
                check=True,
                capture_output=True,
            )
            .stdout.decode("ascii")
            .strip()
        )

        ld_filepath = (
            subprocess.run(
                f"realpath $(find . -name 'ld-*.so')",
                cwd=tmp_dirpath,
                shell=True,
                check=True,
                capture_output=True,
            )
            .stdout.decode("ascii")
            .strip()
        )

        libc_arch = match.group("arch")
        libc_version = match.group("version")

        proper_libc_filename = f"libc-{libc_arch}-{libc_version}.so"
        proper_libc_filepath = os.path.join(bowkin.libcs_dirpath, proper_libc_filename)
        shutil.copy2(package_filepath, proper_libc_filepath)

        proper_ld_filename = f"ld-{libc_arch}-{libc_version}.so"
        proper_ld_filepath = os.path.join(bowkin.libcs_dirpath, proper_ld_filename)
        shutil.copy2(package_filepath, proper_ld_filepath)

        print(
            "Added:\n"
            f"- {colorama.Style.BRIGHT}{proper_libc_filepath}{colorama.Style.RESET_ALL}\n"
            f"- {colorama.Style.BRIGHT}{proper_ld_filepath}{colorama.Style.RESET_ALL}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=argparse.FileType())
    args = parser.parse_args()

    package_filepath = args.package.name
    package_filename = os.path.basename(package_filepath)

    # libc6_2.23-0ubuntu10_amd64.deb
    match = re.match(
        "libc6_(?P<version>\d.\d+-\dubuntu\d+)_(?P<arch>i386|amd64).deb",
        package_filename,
    )
    if match:
        extract_ld_and_libc(package_filepath, match)
        raise SystemExit

    # libc6_2.24-11+deb9u3_amd64.deb
    match = re.match(
        "libc6_(?P<version>\d.\d+-\d+\+deb\du\d)_(?P<arch>i386|amd64).deb",
        package_filename,
    )
    if match:
        extract_ld_and_libc(package_filepath, match)
        raise SystemExit

    # glibc-2.27-2-x86_64.pkg.tar.xz
    match = re.match(
        "glibc-(?P<version>\d.\d+-\d)-(?P<arch>i686|x86_64).pkg.tar.xz",
        package_filename,
    )
    if match:
        extract_ld_and_libc(package_filepath, match)
        raise SystemExit
