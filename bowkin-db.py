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

# ############################################################################ #


def add(package_filepath, dest_dirpath=bowkin.libcs_dirpath):
    package_filename = os.path.basename(package_filepath)

    # e.g. libc6_2.23-0ubuntu10_amd64.deb or libc6_2.24-11+deb9u3_amd64.deb
    matches = [
        re.match(pattern, package_filename)
        for pattern in (
            "libc6(?:-dbg)?_(?P<version>.*?(ubuntu|deb).*?)_(?P<arch>i386|amd64|armel|armhf|arm64).deb",
            "glibc-(?P<version>\d.\d+-\d+)-(?P<arch>i686|x86_64).pkg.tar.xz",
        )
    ]

    try:
        match = next(match for match in matches if match is not None)
    except StopIteration:
        return
    extract(package_filepath, match, dest_dirpath)


def extract(package_filepath, match, dest_dirpath):
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

        # extract ld
        ld_filepath = extract_ld_filepath(tmp_dirpath)
        if ld_filepath:
            proper_ld_filename = f"ld-{libc_arch}-{libc_version}.so"
            proper_ld_filepath = os.path.join(dest_dirpath, proper_ld_filename)
            shutil.copy2(ld_filepath, proper_ld_filepath)
            ld_relpath = os.path.relpath(proper_ld_filepath, bowkin.libcs_dirpath)
            print(
                f"Saved: {colorama.Style.BRIGHT}.../{ld_relpath}{colorama.Style.RESET_ALL}"
            )

        # extract libc
        libc_filepath = extract_libc_filepath(tmp_dirpath)
        if libc_filepath:
            proper_libc_filename = f"libc-{libc_arch}-{libc_version}.so"
            proper_libc_filepath = os.path.join(dest_dirpath, proper_libc_filename)
            shutil.copy2(libc_filepath, proper_libc_filepath)
            libc_relpath = os.path.relpath(proper_libc_filepath, bowkin.libcs_dirpath)
            print(
                f"Saved: {colorama.Style.BRIGHT}.../{libc_relpath}{colorama.Style.RESET_ALL}"
            )

        # extract libc symbols
        libc_symbols_filepath = extract_libc_symbols_filepath(tmp_dirpath)
        if libc_symbols_filepath:
            proper_libc_symbols_filename = f"libc-{libc_arch}-{libc_version}.so.debug"
            proper_libc_symbols_filepath = os.path.join(
                dest_dirpath, proper_libc_symbols_filename
            )
            shutil.copy2(libc_symbols_filepath, proper_libc_symbols_filepath)
            libc_symbols_relpath = os.path.relpath(
                proper_libc_symbols_filepath, bowkin.libcs_dirpath
            )
            print(
                f"Saved: {colorama.Style.BRIGHT}.../{libc_symbols_relpath}{colorama.Style.RESET_ALL}"
            )


def extract_ld_filepath(tmp_dirpath):
    ld_filepath = None
    for path in (
        "lib/aarch64-linux-gnu/ld-*.so",
        "lib/arm-linux-gnueabihf/ld-*.so",
        "lib/arm-linux-gnueabi/ld-*.so",
        "lib/i386-linux-gnu/ld-*.so",
        "lib/x86_64-linux-gnu/ld-*.so",
        "usr/lib/ld-*.so",
    ):
        ld_filepaths = glob.glob(os.path.join(tmp_dirpath, path))
        if ld_filepaths:
            assert len(ld_filepaths) == 1
            ld_filepath = ld_filepaths[0]
            return ld_filepath
    return None


def extract_libc_filepath(tmp_dirpath):
    libc_filepath = None
    for path in (
        "lib/aarch64-linux-gnu/libc-*.so",
        "lib/arm-linux-gnueabihf/libc-*.so",
        "lib/arm-linux-gnueabi/libc-*.so",
        "lib/i386-linux-gnu/libc-*.so",
        "lib/x86_64-linux-gnu/libc-*.so",
        "usr/lib/libc-*.so",
    ):
        libc_filepaths = glob.glob(os.path.join(tmp_dirpath, path))
        if libc_filepaths:
            assert len(libc_filepaths) == 1
            libc_filepath = libc_filepaths[0]
            return libc_filepath
    return None


def extract_libc_symbols_filepath(tmp_dirpath):
    libc_symbols_filepath = None
    for path in (
        "usr/lib/debug/lib/i386-linux-gnu/libc-*.so",
        "usr/lib/debug/lib/x86_64-linux-gnu/libc-*.so",
    ):
        libc_symbols_filepaths = glob.glob(os.path.join(tmp_dirpath, path))
        if libc_symbols_filepaths:
            assert len(libc_symbols_filepaths) == 1
            libc_symbols_filepath = libc_symbols_filepaths[0]
            return libc_symbols_filepath
    return None


# ############################################################################ #


def bootstrap():
    if not utils.query_yes_no(
        "This operation will download a bunch of libcs into"
        f" {colorama.Style.BRIGHT}{bowkin.libcs_dirpath}{colorama.Style.RESET_ALL}. Proceed?"
    ):
        utils.abort("Aborted by user.")

    # Ubuntu
    distro_dirpath = os.path.join(bowkin.libcs_dirpath, "ubuntu")
    os.makedirs(distro_dirpath, exist_ok=True)
    for release in ("trusty", "xenial", "artful", "bionic"):
        release_dirpath = os.path.join(distro_dirpath, release)
        os.makedirs(release_dirpath, exist_ok=True)
        for arch in ("i386", "amd64"):
            for package in ("libc6", "libc6-dbg"):
                print()
                url = f"https://packages.ubuntu.com/{release}/{arch}/{package}/download"
                package_url = extract_package_url_ubuntu_debian(url)
                if not package_url:
                    continue
                with tempfile.TemporaryDirectory() as tmp_dirpath:
                    package_filepath = utils.download(tmp_dirpath, package_url)
                    add(package_filepath, dest_dirpath=release_dirpath)

    # Debian
    distro_dirpath = os.path.join(bowkin.libcs_dirpath, "debian")
    os.makedirs(distro_dirpath, exist_ok=True)
    for release in ("squeeze", "wheezy", "jessie", "stretch"):
        release_dirpath = os.path.join(distro_dirpath, release)
        os.makedirs(release_dirpath, exist_ok=True)
        for arch in ("i386", "amd64"):
            for package in ("libc6", "libc6-dbg"):
                print()
                url = f"https://packages.debian.org/{release}/{arch}/{package}/download"
                package_url = extract_package_url_ubuntu_debian(url)
                if not package_url:
                    continue
                with tempfile.TemporaryDirectory() as tmp_dirpath:
                    package_filepath = utils.download(tmp_dirpath, package_url)
                    add(package_filepath, dest_dirpath=release_dirpath)

    # Arch Linux
    distro_dirpath = os.path.join(bowkin.libcs_dirpath, "arch")
    os.makedirs(distro_dirpath, exist_ok=True)
    for arch in ("i686", "x86_64"):
        url = "https://archive.archlinux.org/packages/g/glibc/"
        for package_url in extract_package_urls_arch(url, arch):
            print()
            with tempfile.TemporaryDirectory() as tmp_dirpath:
                package_filepath = utils.download(tmp_dirpath, package_url)
                add(package_filepath, dest_dirpath=distro_dirpath)


def extract_package_url_ubuntu_debian(url):
    with urllib.request.urlopen(url) as u:
        try:
            package_url = (
                re.search(br"['\"](?P<url>https?.*?libc6.*?.deb)['\"]", u.read())
                .group("url")
                .decode("ascii")
            )
            return package_url
        except AttributeError:
            print(
                f"{colorama.Style.BRIGHT}{colorama.Fore.RED}Problems on: {url}{colorama.Style.RESET_ALL}"
            )
            return None


def extract_package_urls_arch(url, arch):
    with urllib.request.urlopen(url) as u:
        try:
            package_filenames = re.findall(
                fr"['\"](?P<package_filename>glibc-(?:.*?)-{arch}\.pkg\.tar\.[gx]z)['\"]",
                u.read().decode("ascii"),
            )
            package_urls = [
                os.path.join(url, package_filename)
                for package_filename in package_filenames
            ]
            return package_urls
        except AttributeError:
            print(
                f"{colorama.Style.BRIGHT}{colorama.Fore.RED}Problems on: {url}{colorama.Style.RESET_ALL}"
            )
            return []


# ############################################################################ #


def rebuild():
    with sqlite3.connect(bowkin.libcs_db_filepath) as conn:
        conn.execute("DROP TABLE IF EXISTS libcs")
        conn.execute(
            "CREATE TABLE libcs"
            "(relpath text, architecture text, distro text, release text, version text, buildID text,"
            "PRIMARY KEY(version, buildID))"
        )

        for filepath in glob.glob(f"{bowkin.libcs_dirpath}/**", recursive=True):
            match = re.match(
                r"(?:.*)libcs/(?P<relpath>(?P<distro>.+?)?/?(?:(?P<release>.+?)/)?libc-(?P<architecture>i386|i686|amd64|x86_64|armel|armhf|arm64)-(?P<version>.+?).so)$",
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


# ############################################################################ #

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
        rebuild()
    elif args.action == "bootstrap":
        bootstrap()
        rebuild()
    elif args.action == "rebuild":
        rebuild()
