#!/usr/bin/env python3
import argparse
import collections
import glob
import json
import os
import pprint
import re
import sqlite3
import subprocess
import sys

import elftools.elf.elffile


def build_db():
    with sqlite3.connect("libcs.db") as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS libcs"
            "(architecture text, distro text, release text, version text, buildID text, filepath text)"
        )

        conn.execute("DELETE FROM libcs")

        for filepath in glob.glob("libcs/**/libc*.so", recursive=True):
            if "dbg" in os.path.basename(filepath):
                continue
            m = re.match(
                r"libcs/(?P<distro>.+?)/(?:(?P<release>.+?)/)?libc-(?P<architecture>i386|i686|amd64|x86_64|armel|armhf|arm64)-(?P<version>.+?).so",
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
    output = subprocess.check_output("file {}".format(libc_filepath), shell=True)
    output = output.strip().decode("ascii")
    buildID = re.search("BuildID\[sha1\]\=(.*?),", output).group(1)
    return buildID


def identify(libc_filepath):
    with sqlite3.connect("libcs.db") as conn:
        return [
            libc
            for libc in conn.execute(
                "SELECT * FROM libcs where buildID=?",
                (extract_buildID_from_file(libc_filepath),),
            )
        ]


def find(symbols):
    matches = []
    with sqlite3.connect("libcs.db") as conn:
        for libc in conn.execute("SELECT * FROM libcs"):
            _, _, _, _, _, filepath = libc
            with open(filepath, "rb") as f:
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
                    matches.append(libc)
    return matches


################################################################################


def symbol_address_pair(text):
    symbol, address = text.split("=")
    offset = int(address, 16) & 0b111111111111
    return (symbol, offset)


################################################################################

os.chdir(sys.path[0])

build_db()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True

    identify_parser = subparsers.add_parser("identify")
    identify_parser.add_argument("libc", type=argparse.FileType())

    find_parser = subparsers.add_parser("find")
    find_parser.add_argument(
        "symbols", type=symbol_address_pair, nargs="+", metavar="symbol=address"
    )

    args = parser.parse_args()

    if args.action == "identify":
        for _, _, _, _, _, filepath in identify(args.libc.name):
            print(filepath)
    elif args.action == "find":
        for _, _, _, _, _, filepath in find(args.symbols):
            print(filepath)
