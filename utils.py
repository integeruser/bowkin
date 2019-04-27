#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
import urllib.request

import colorama
import elftools.elf.elffile


def abort(message):
    print(
        f"{colorama.Style.BRIGHT}{colorama.Fore.RED}{message}{colorama.Style.RESET_ALL}"
    )
    raise SystemExit


def make_bright(text):
    return f"{colorama.Style.BRIGHT}{text}{colorama.Style.RESET_ALL}"


def make_warning(text):
    return f"{colorama.Fore.YELLOW}{text}{colorama.Style.RESET_ALL}"


def query_yes_no(question):
    return input("{} (y/[N]) ".format(question)).lower() in ("y", "yes")


def extract_buildID_from_file(libc_filepath):
    out = subprocess.check_output(
        shlex.split("file {}".format(shlex.quote(libc_filepath)))
    )
    try:
        buildID = (
            re.search(br"BuildID\[sha1\]\=(?P<buildID>[a-z0-9]+)", out)
            .group("buildID")
            .decode("ascii")
        )
        return buildID
    except AttributeError:
        return None


def get_libc_dbg_proper_filename(libc_filepath):
    with open(libc_filepath, "rb") as f:
        elf = elftools.elf.elffile.ELFFile(f)
        data = elf.get_section_by_name(".gnu_debuglink").data()
        libc_dbg_filename = data[: data.index(b"\0")].decode("ascii")
        return libc_dbg_filename


def retrieve(url, dirpath=None):
    if not dirpath:
        with urllib.request.urlopen(url) as u:
            return u.read()
    else:
        print(f"Downloading: {colorama.Style.BRIGHT}{url}{colorama.Style.RESET_ALL}")
        filepath, _ = urllib.request.urlretrieve(
            url, filename=os.path.join(dirpath, os.path.basename(url))
        )
        return filepath


# ############################################################################ #


def dump(libc):
    libc["realpath"] = os.path.realpath(
        os.path.join(get_libcs_dirpath(), libc["relpath"])
    )
    print(json.dumps(libc, sort_keys=True, indent=4))


# ############################################################################ #


def get_libcs_dirpath():
    # bowkin assumes either the directory `libcs` or a symlink to it can be found
    # in the same directory of this script
    libcs_dirpath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "libcs")
    return libcs_dirpath


def get_libcs_db_filepath():
    libcs_db_filepath = os.path.join(os.path.dirname(get_libcs_dirpath()), "libcs.db")
    return libcs_db_filepath


# ############################################################################ #


def match(package_filepath):
    package_filename = os.path.basename(package_filepath)
    # Examples of supported packages:
    # - libc6_2.23-0ubuntu10_amd64.deb
    # - libc6_2.24-11+deb9u3_amd64.deb
    # - glibc-2.23-3-x86_64.pkg.tar.xz
    for pattern in (
        r"libc6(?:-dbg)?_(?P<version>\d.\d+)-(?P<patch>\d+ubuntu\d+)_(?P<architecture>i386|amd64|armel|armhf|arm64).deb",
        r"libc6(?:-dbg)?_(?P<version>\d.\d+)-(?P<patch>\d+\+deb.+?)_(?P<architecture>i386|amd64|armel|armhf|arm64).deb",
        r"glibc-(?P<version>\d.\d+)-(?P<patch>\d+)-(?P<architecture>i686|x86_64).pkg.tar.xz",
    ):
        match = re.match(pattern, package_filename)
        if match:
            return match
    else:
        return None
