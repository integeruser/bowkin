#!/usr/bin/env python3
import argparse
import glob
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request

import utils

# ############################################################################ #


def add(package_filepath, dest_dirpath=utils.get_libcs_dirpath()):
    print(utils.make_bright("<add>"))

    package_filename = os.path.basename(package_filepath)

    # examples of supported packages:
    # - libc6_2.23-0ubuntu10_amd64.deb
    # - libc6_2.24-11+deb9u3_amd64.deb
    # - glibc-2.23-3-x86_64.pkg.tar.xz
    matches = [
        re.match(pattern, package_filename)
        for pattern in (
            "libc6(?:-dbg)?_(?P<version>.*?(ubuntu|deb)?.*?)_(?P<architecture>i386|amd64|armel|armhf|arm64).deb",
            "glibc-(?P<version>\d.\d+-\d+)-(?P<architecture>i686|x86_64).pkg.tar.xz",
        )
    ]

    try:
        match = next(match for match in matches if match is not None)
    except StopIteration:
        utils.abort(
            f"Aborting: the filename of the package did not match any supported patterns."
        )

    libc_architecture = match.group("architecture")
    libc_version = match.group("version")

    tmp_dirpath = extract(package_filepath)

    # find and add ld
    ld_search_paths = [
        os.path.join(tmp_dirpath, subpath)
        for subpath in (
            "lib/aarch64-linux-gnu/ld-*.so",
            "lib/arm-linux-gnueabihf/ld-*.so",
            "lib/arm-linux-gnueabi/ld-*.so",
            "lib/i386-linux-gnu/ld-*.so",
            "lib/x86_64-linux-gnu/ld-*.so",
            "usr/lib/ld-*.so",
        )
    ]
    new_ld_filename = f"ld-{libc_architecture}-{libc_version}.so"
    new_ld_filepath = find_matching_file_and_add_to_db(
        ld_search_paths, dest_dirpath, new_ld_filename
    )

    # find and add libc
    libc_search_paths = [
        os.path.join(tmp_dirpath, subpath)
        for subpath in (
            "lib/aarch64-linux-gnu/libc-*.so",
            "lib/arm-linux-gnueabihf/libc-*.so",
            "lib/arm-linux-gnueabi/libc-*.so",
            "lib/i386-linux-gnu/libc-*.so",
            "lib/x86_64-linux-gnu/libc-*.so",
            "usr/lib/libc-*.so",
        )
    ]
    new_libc_filename = f"libc-{libc_architecture}-{libc_version}.so"
    new_libc_filepath = find_matching_file_and_add_to_db(
        libc_search_paths, dest_dirpath, new_libc_filename
    )

    # find and add libc symbols
    libc_symbols_search_paths = [
        os.path.join(tmp_dirpath, subpath)
        for subpath in (
            "usr/lib/debug/lib/i386-linux-gnu/libc-*.so",
            "usr/lib/debug/lib/x86_64-linux-gnu/libc-*.so",
        )
    ]
    new_libc_symbols_filename = f"libc-{libc_architecture}-{libc_version}.so.debug"
    new_libc_symbols_filepath = find_matching_file_and_add_to_db(
        libc_symbols_search_paths, dest_dirpath, new_libc_symbols_filename
    )

    if not any((new_ld_filepath, new_libc_filepath, new_libc_symbols_filepath)):
        print(
            utils.make_warning(
                f"Skipping: the package seems to not contain a dynamic loader, libc or debug symbols."
            )
        )
        return

    # keep the package, it may be useful later
    shutil.copy2(package_filepath, dest_dirpath)

    print(utils.make_bright("</add>"))


def find_matching_file_and_add_to_db(search_paths, dest_dirpath, new_filename):
    filepath = find_matching_file(search_paths)
    if not filepath:
        return None

    new_filepath = os.path.join(dest_dirpath, new_filename)
    shutil.copy2(filepath, new_filepath)

    relpath = os.path.relpath(new_filepath, utils.get_libcs_dirpath())

    print(f"Added: {utils.make_bright(f'.../{relpath}')}")
    return new_filepath


def find_matching_file(paths):
    for path in paths:
        filepaths = glob.glob(path)
        if filepaths:
            assert len(filepaths) == 1
            filepath = filepaths[0]
            return filepath
    return None


# ############################################################################ #


def bootstrap(ubuntu_only):
    print(utils.make_bright("<bootstrap>"))

    if not utils.query_yes_no(
        "This operation will download a bunch of libcs into"
        f" {utils.make_bright(utils.get_libcs_dirpath())}. Proceed?"
    ):
        utils.abort("Aborted by user.")

    add_ubuntu_libcs()
    if not ubuntu_only:
        add_debian_libcs()
        add_arch_linux_libcs()

    print(utils.make_bright("</bootstrap>"))


def add_ubuntu_libcs():
    distro_dirpath = os.path.join(utils.get_libcs_dirpath(), "ubuntu")
    os.makedirs(distro_dirpath, exist_ok=True)
    for release in ("trusty", "xenial", "artful", "bionic", "buster"):
        release_dirpath = os.path.join(distro_dirpath, release)
        os.makedirs(release_dirpath, exist_ok=True)
        for architecture in ("i386", "amd64"):
            for package in ("libc6", "libc6-dbg"):
                print()
                url = f"https://packages.ubuntu.com/{release}/{architecture}/{package}/download"
                package_url = extract_package_url_ubuntu_debian(url)
                if not package_url:
                    continue
                with tempfile.TemporaryDirectory() as tmp_dirpath:
                    package_filepath = utils.download(tmp_dirpath, package_url)
                    add(package_filepath, dest_dirpath=release_dirpath)


def add_debian_libcs():
    distro_dirpath = os.path.join(utils.get_libcs_dirpath(), "debian")
    os.makedirs(distro_dirpath, exist_ok=True)
    for release in ("squeeze", "wheezy", "jessie", "stretch"):
        release_dirpath = os.path.join(distro_dirpath, release)
        os.makedirs(release_dirpath, exist_ok=True)
        for architecture in ("i386", "amd64"):
            for package in ("libc6", "libc6-dbg"):
                print()
                url = f"https://packages.debian.org/{release}/{architecture}/{package}/download"
                package_url = extract_package_url_ubuntu_debian(url)
                if not package_url:
                    continue
                with tempfile.TemporaryDirectory() as tmp_dirpath:
                    package_filepath = utils.download(tmp_dirpath, package_url)
                    add(package_filepath, dest_dirpath=release_dirpath)


def add_arch_linux_libcs():
    distro_dirpath = os.path.join(utils.get_libcs_dirpath(), "arch")
    os.makedirs(distro_dirpath, exist_ok=True)
    for architecture in ("i686", "x86_64"):
        url = "https://archive.archlinux.org/packages/g/glibc/"
        for package_url in extract_package_urls_arch(url, architecture):
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
        print(utils.make_warning(f"Problems on: {url}"))
        return None
    except urllib.error.HTTPError:
        print(utils.make_warning(f"HTTP Error on: {url}"))
        return None


def extract_package_urls_arch(url, architecture):
    with urllib.request.urlopen(url) as u:
        try:
            package_filenames = re.findall(
                fr"['\"](?P<package_filename>glibc-(?:.*?)-{architecture}\.pkg\.tar\.[gx]z)['\"]",
                u.read().decode("ascii"),
            )
            package_urls = [
                os.path.join(url, package_filename)
                for package_filename in package_filenames
            ]
            return package_urls
        except AttributeError:
            print(utils.make_warning(f"Problems on: {url}"))
            return []


# ############################################################################ #


def extract(package_filepath):
    print(utils.make_bright("<extract>"))

    package_filename = os.path.basename(package_filepath)

    tmp_dirpath = tempfile.mkdtemp()
    shutil.copy2(package_filepath, tmp_dirpath)
    # extract the package
    subprocess.run(
        f"ar x {shlex.quote(package_filename)}",
        cwd=tmp_dirpath,
        check=True,
        shell=True,
        stderr=subprocess.PIPE,
    )
    # extract data.tar.?z if it exists
    subprocess.run(
        f"if [ -f data.tar.?z ]; then tar xf data.tar.?z; fi",
        cwd=tmp_dirpath,
        check=True,
        shell=True,
    )
    print(f"Extracted: {utils.make_bright(tmp_dirpath)}")

    print(utils.make_bright("</extract>"))
    return tmp_dirpath


# ############################################################################ #


def rebuild():
    print(utils.make_bright("<rebuild>"))

    with sqlite3.connect(utils.get_libcs_db_filepath()) as conn:
        conn.execute("DROP TABLE IF EXISTS libcs")
        conn.execute(
            "CREATE TABLE libcs"
            "(relpath text, architecture text, distro text, release text, version text, patch text, buildID text)"
        )

        for filepath in glob.glob(f"{utils.get_libcs_dirpath()}/**", recursive=True):
            match = re.match(
                r"(?:.*?)libcs/(?:(?P<distro>.+?)/)?(?:(?P<release>.+?)/)?libc-(?P<architecture>i386|i686|amd64|x86_64|armel|armhf|arm64)-(?P<version>\d.\d+)(?:-(?P<patch>.+?))?\.so$",
                filepath,
            )
            if match:
                relpath = os.path.relpath(filepath, utils.get_libcs_dirpath())
                print(f"Processing: {utils.make_bright(f'.../{relpath}')}")
                conn.execute(
                    "INSERT INTO libcs VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        relpath,
                        match.group("architecture"),
                        match.group("distro"),
                        match.group("release"),
                        match.group("version"),
                        match.group("patch"),
                        utils.extract_buildID_from_file(filepath),
                    ),
                )

    print(utils.make_bright("</rebuild>"))


# ############################################################################ #

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")

    add_parser = subparsers.add_parser(
        "add",
        help="add to the libs folder the libc and the loader from the specified packet",
    )
    add_parser.add_argument("package", type=argparse.FileType())

    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="will download some libcs used in ubuntu, debian and arch linux",
    )
    bootstrap_parser.add_argument("--ubuntu-only", action="store_true")

    extract_parser = subparsers.add_parser(
        "extract", help="Extract a package into a temporary directory"
    )
    extract_parser.add_argument("package", type=argparse.FileType())

    rebuild_parser = subparsers.add_parser(
        "rebuild", help="will rebuild the database using the added libcs"
    )

    args = parser.parse_args()

    if args.action == "add":
        add(args.package.name)
        rebuild()
    elif args.action == "bootstrap":
        bootstrap(args.ubuntu_only)
        rebuild()
    elif args.action == "extract":
        extract(args.package.name)
    elif args.action == "rebuild":
        rebuild()
    else:
        parser.print_help(sys.stderr)
