#!/usr/bin/env python3
import argparse
import glob
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import tempfile
import urllib.request

import colorama

import bowkin
import utils


def add(package_filepath, ask_confirmation=True, dest_dirpath=bowkin.libcs_dirpath):
    package_filename = os.path.basename(package_filepath)

    # e.g. libc6_2.23-0ubuntu10_amd64.deb or libc6_2.24-11+deb9u3_amd64.deb
    matches = [
        re.match(pattern, package_filename)
        for pattern in (
            "libc6(?:-dbg)?_(?P<version>.*?(ubuntu|deb).*?)_(?P<arch>i386|amd64).deb",
            "glibc-(?P<version>\d.\d+-\d)-(?P<arch>i686|x86_64).pkg.tar.xz",
        )
    ]

    try:
        match = next(match for match in matches if match is not None)
    except StopIteration:
        return
    extract(package_filepath, match, ask_confirmation, dest_dirpath)


def extract(package_filepath, match, ask_confirmation, dest_dirpath):
    print(f"Extracting: {package_filepath}")

    package_filename = os.path.basename(package_filepath)
    libc_arch = match.group("arch")
    libc_version = match.group("version")

    with tempfile.TemporaryDirectory() as tmp_dirpath:
        shutil.copy2(package_filepath, tmp_dirpath)

        subprocess.run(
            f"tar xf {shlex.quote(package_filename)}",
            cwd=tmp_dirpath,
            shell=True,
            check=True,
        )
        subprocess.run(
            f"if [ -f data.tar.?z ]; then tar xf data.tar.?z; fi",
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
            proper_libc_filepath = os.path.join(dest_dirpath, proper_libc_filename)
            if not ask_confirmation or utils.query_yes_no(
                f"Copy it to {colorama.Style.BRIGHT}{proper_libc_filepath}{colorama.Style.RESET_ALL}?"
            ):
                shutil.copy2(libc_filepath, proper_libc_filepath)
                print(
                    f"Saved: {colorama.Style.BRIGHT}{proper_libc_filepath}{colorama.Style.RESET_ALL}"
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
                    f"Found ld: {colorama.Style.BRIGHT}{ld_filepath}{colorama.Style.RESET_ALL}"
                )
            proper_ld_filename = f"ld-{libc_arch}-{libc_version}.so"
            if debug_symbols:
                proper_ld_filename += ".debug"
            proper_ld_filepath = os.path.join(dest_dirpath, proper_ld_filename)
            if not ask_confirmation or utils.query_yes_no(
                f"Copy it to {colorama.Style.BRIGHT}{proper_ld_filepath}{colorama.Style.RESET_ALL}?"
            ):
                shutil.copy2(ld_filepath, proper_ld_filepath)
                print(
                    f"Saved: {colorama.Style.BRIGHT}{proper_ld_filepath}{colorama.Style.RESET_ALL}"
                )


def bootstrap():
    if not utils.query_yes_no(
        "This operation will download a bunch of libcs into"
        f" {colorama.Style.BRIGHT}{bowkin.libcs_dirpath}{colorama.Style.RESET_ALL}. Proceed?"
    ):
        utils.abort("Aborted by user.")

    os_dirpath = os.path.join(bowkin.libcs_dirpath, "ubuntu")
    os.makedirs(os_dirpath, exist_ok=True)
    for distro in ("trusty", "xenial", "artful", "bionic"):
        distro_dirpath = os.path.join(os_dirpath, distro)
        os.makedirs(distro_dirpath, exist_ok=True)
        for arch in ("i386", "amd64"):
            for package in ("libc6", "libc6-dbg"):
                with urllib.request.urlopen(
                    f"https://packages.ubuntu.com/{distro}/{arch}/{package}/download"
                ) as u:
                    content = u.read()
                    try:
                        package_url = (
                            re.search(
                                br"['\"](?P<url>https?.*?libc6.*?.deb)['\"]", content
                            )
                            .group("url")
                            .decode("ascii")
                        )
                        with tempfile.TemporaryDirectory() as tmp_dirpath:
                            package_filepath = utils.download(tmp_dirpath, package_url)
                            add(
                                package_filepath,
                                ask_confirmation=False,
                                dest_dirpath=distro_dirpath,
                            )
                    except AttributeError:
                        print(f"problems on {url}")


def rebuild():
    with sqlite3.connect(bowkin.libcs_db_filepath) as conn:
        conn.execute("DROP TABLE IF EXISTS libcs")
        conn.execute(
            "CREATE TABLE libcs"
            "(relpath text, architecture text, distro text, release text, version text, buildID text,"
            "PRIMARY KEY(version, buildID))"
        )

        for filepath in glob.glob(f"{bowkin.libcs_dirpath}/**/*", recursive=True):
            # TODO improve
            match = re.match(
                r"(?:.*)libcs/(?P<relpath>(?P<distro>.+?)/(?:(?P<release>.+?)/)?libc-(?P<architecture>i386|i686|amd64|x86_64|armel|armhf|arm64)-(?P<version>.+?).so)$",
                filepath,
            )
            if match:
                conn.execute(
                    "INSERT INTO libcs VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        match.group("relpath"),
                        match.group("architecture"),
                        match.group("distro"),
                        match.group("release"),
                        match.group("version"),
                        utils.extract_buildID_from_file(filepath),
                    ),
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("package", type=argparse.FileType())

    bootstrap_parser = subparsers.add_parser("bootstrap")

    rebuild_parser = subparsers.add_parser("rebuild")

    args = parser.parse_args()

    if args.action == "add":
        add(args.package.name)
    elif args.action == "bootstrap":
        bootstrap()
    elif args.action == "rebuild":
        rebuild()
