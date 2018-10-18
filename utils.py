#!/usr/bin/env python3
import re
import shlex
import subprocess

import elftools.elf.elffile


def abort(message=None):
    if not message:
        message = "Aborted."
    print(
        f"{colorama.Style.BRIGHT}{colorama.Fore.RED}{message}{colorama.Style.RESET_ALL}"
    )
    raise SystemExit


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
