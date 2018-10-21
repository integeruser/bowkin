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
import utils


def extract_ld_and_libc(package_filepath, match):
    libc_arch = match.group("arch")
    libc_version = match.group("version")

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
                f"realpath $(find . -name 'libc-*.so')",
                cwd=tmp_dirpath,
                shell=True,
                check=True,
                capture_output=True,
            )
            .stdout.decode("ascii")
            .strip()
        )
        if libc_filepath:
            debug_symbols = "dbg" in package_filename or "debug" in os.path.relpath(
                libc_filepath, tmp_dirpath
            )
            if debug_symbols:
                print(
                    f"Found debug symbols: {colorama.Style.BRIGHT}{libc_filepath}{colorama.Style.RESET_ALL}"
                )
            else:
                print(
                    f"Found libc: {colorama.Style.BRIGHT}{libc_filepath}{colorama.Style.RESET_ALL}"
                )
            proper_libc_filename = f"libc-{libc_arch}-{libc_version}.so"
            if debug_symbols:
                proper_libc_filename += ".debug"
            proper_libc_filepath = os.path.join(
                bowkin.libcs_dirpath, proper_libc_filename
            )
            if utils.query_yes_no(
                f"Copy it to {colorama.Style.BRIGHT}{proper_libc_filepath}{colorama.Style.RESET_ALL}?"
            ):
                shutil.copy2(libc_filepath, proper_libc_filepath)

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
        if ld_filepath:
            debug_symbols = "dbg" in package_filename or "debug" in os.path.relpath(
                ld_filepath, tmp_dirpath
            )
            if debug_symbols:
                print(
                    f"Found debug symbols: {colorama.Style.BRIGHT}{ld_filepath}{colorama.Style.RESET_ALL}"
                )
            else:
                print(
                    f"Found libc: {colorama.Style.BRIGHT}{ld_filepath}{colorama.Style.RESET_ALL}"
                )
            proper_ld_filename = f"ld-{libc_arch}-{libc_version}.so"
            if debug_symbols:
                proper_ld_filename += ".debug"
            proper_ld_filepath = os.path.join(bowkin.libcs_dirpath, proper_ld_filename)
            if utils.query_yes_no(
                f"Copy it to {colorama.Style.BRIGHT}{proper_ld_filepath}{colorama.Style.RESET_ALL}?"
            ):
                shutil.copy2(ld_filepath, proper_ld_filepath)


def add(package_filepath):
    package_filename = os.path.basename(package_filepath)

    # libc6_2.23-0ubuntu10_amd64.deb
    match = re.match(
        "libc6(?:-dbg)_(?P<version>\d.\d+-\dubuntu\d+)_(?P<arch>i386|amd64).deb",
        package_filename,
    )
    if match:
        extract_ld_and_libc(package_filepath, match)
        return

    # libc6_2.24-11+deb9u3_amd64.deb
    match = re.match(
        "libc6(?:-dbg)_(?P<version>\d.\d+-\d+\+deb\du\d)_(?P<arch>i386|amd64).deb",
        package_filename,
    )
    if match:
        extract_ld_and_libc(package_filepath, match)
        return

    # glibc-2.27-2-x86_64.pkg.tar.xz
    match = re.match(
        "glibc-(?P<version>\d.\d+-\d)-(?P<arch>i686|x86_64).pkg.tar.xz",
        package_filename,
    )
    if match:
        extract_ld_and_libc(package_filepath, match)
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("package", type=argparse.FileType())

    args = parser.parse_args()

    if args.action == "add":
        add(args.package.name)