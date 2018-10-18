#!/usr/bin/env python3
import argparse
import glob
import json
import os
import re
import shlex
import sqlite3
import subprocess
import sys

import elftools.elf.elffile


def identify(libc_filepath):
    with sqlite3.connect(libcs_db_filepath) as conn:
        conn.row_factory = sqlite3.Row
        return [
            dict(libc)
            for libc in conn.execute(
                "SELECT * FROM libcs where buildID=?",
                (extract_buildID_from_file(libc_filepath),),
            )
        ]


def find(symbols):
    matches = []
    with sqlite3.connect(libcs_db_filepath) as conn:
        conn.row_factory = sqlite3.Row
        for libc in conn.execute("SELECT * FROM libcs"):
            with open(libc["filepath"], "rb") as f:
                elf = elftools.elf.elffile.ELFFile(f)
                dynsym_section = elf.get_section_by_name(".dynsym")

                for symbol, address in symbols:
                    try:
                        libc_sym = dynsym_section.get_symbol_by_name(symbol)[0]
                        libc_address = libc_sym.entry.st_value & 0b111111111111
                        if libc_address != address:
                            # not a match
                            break
                    except (IndexError, TypeError):
                        break
                else:
                    matches.append(dict(libc))
    return matches


def rebuild():
    with sqlite3.connect(libcs_db_filepath) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS libcs"
            "(architecture text, distro text, release text, version text, buildID text, filepath text)"
        )

        conn.execute("DELETE FROM libcs")

        for filepath in glob.glob(f"{libcs_dirpath}/**/libc*.so", recursive=True):
            if "dbg" in os.path.basename(filepath):
                continue
            m = re.match(
                r"(?:.*)libcs/(?P<distro>.+?)/(?:(?P<release>.+?)/)?libc-(?P<architecture>i386|i686|amd64|x86_64|armel|armhf|arm64)-(?P<version>.+?).so",
                filepath,
            )
            buildID = extract_buildID_from_file(filepath)
            conn.execute(
                "INSERT INTO libcs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    m.group("architecture"),
                    m.group("distro"),
                    m.group("release"),
                    m.group("version"),
                    buildID,
                    filepath,
                ),
            )


################################################################################


def extract_buildID_from_file(libc_filepath):
    output = subprocess.check_output(
        "file {}".format(shlex.quote(libc_filepath)), shell=True
    )
    output = output.strip().decode("ascii")
    buildID = re.search("BuildID\[sha1\]\=(.*?),", output).group(1)
    return buildID


def symbol_address_pair(text):
    symbol, address = text.split("=")
    offset = int(address, 16) & 0b111111111111
    return (symbol, offset)


# bowkin assumes either the directory `libcs` or a symlink to it can be found
# in the same directory of this script
libcs_dirpath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "libcs")
libcs_db_filepath = os.path.join(libcs_dirpath, "libcs.db")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True

    find_parser = subparsers.add_parser("find")
    find_parser.add_argument(
        "symbols", type=symbol_address_pair, nargs="+", metavar="symbol=address"
    )

    identify_parser = subparsers.add_parser("identify")
    identify_parser.add_argument("libc", type=argparse.FileType())

    rebuild_parser = subparsers.add_parser("rebuild")

    args = parser.parse_args()

    if args.action == "find":
        for libc in find(args.symbols):
            print(json.dumps(libc, sort_keys=True, indent=4))
    elif args.action == "identify":
        for libc in identify(args.libc.name):
            print(json.dumps(libc, sort_keys=True, indent=4))
    elif args.action == "rebuild":
        rebuild()
