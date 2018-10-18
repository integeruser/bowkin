#!/usr/bin/env python3
import argparse
import glob
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys

import colorama
import elftools.elf.elffile

import utils


def identify(libc_filepath):
    with sqlite3.connect(libcs_db_filepath) as conn:
        conn.row_factory = sqlite3.Row
        return [
            dict(libc)
            for libc in conn.execute(
                "SELECT * FROM libcs where buildID=?",
                (utils.extract_buildID_from_file(libc_filepath),),
            )
        ]


def find(symbols):
    matches = []
    with sqlite3.connect(libcs_db_filepath) as conn:
        conn.row_factory = sqlite3.Row
        for libc in conn.execute("SELECT * FROM libcs"):
            libc_filepath = os.path.join(libcs_dirpath, libc["relpath"])
            with open(libc_filepath, "rb") as f:
                elf = elftools.elf.elffile.ELFFile(f)
                dynsym_section = elf.get_section_by_name(".dynsym")
                for symbol, address in symbols:
                    offset = int(address, 16) & 0b111111111111
                    try:
                        libc_symbol = dynsym_section.get_symbol_by_name(symbol)[0]
                        libc_offset = libc_symbol.entry.st_value & 0b111111111111
                        if libc_offset != offset:
                            break
                    except (IndexError, TypeError):
                        break
                else:
                    matches.append(dict(libc))
    return matches


def patchelf(binary_filepath, supplied_libc_filepath):
    binary_dirpath = os.path.dirname(binary_filepath)

    # identify the supplied libc
    matches = identify(supplied_libc_filepath)
    if not matches:
        utils.abort("The supplied libc is not in the database.")
    # TODO pick the first for now
    libc = matches[0]

    libc_filepath = os.path.join(libcs_dirpath, libc["relpath"])
    libc_version = libc["version"]

    ld_filepath = os.path.join(
        os.path.dirname(libc_filepath),
        os.path.basename(libc_filepath).replace("libc-", "ld-"),
    )
    # if the dynamic loader does not exist, abort (don't care about race conditions)
    if not os.path.isfile(ld_filepath):
        utils.abort(
            "The dynamic loader corresponding to the libc to use cannot be found."
            f" It should reside at {colorama.Style.BRIGHT}{ld_filepath}{colorama.Style.RESET_ALL}"
        )

    # copy the dynamic loader and the libc to the directory where the binary is located
    libs_dirpath = os.path.join(binary_dirpath, "libs")
    if not utils.query_yes_no(
        "Copy:\n"
        f"- {colorama.Style.BRIGHT}{ld_filepath}{colorama.Style.RESET_ALL}\n"
        f"- {colorama.Style.BRIGHT}{libc_filepath}{colorama.Style.RESET_ALL}\n"
        f"to {colorama.Style.BRIGHT}{libs_dirpath}{colorama.Style.RESET_ALL}?"
    ):
        utils.abort()
    os.makedirs(libs_dirpath, exist_ok=True)
    shutil.copy2(ld_filepath, libs_dirpath)
    shutil.copy2(libc_filepath, libs_dirpath)

    print()

    # if debug symbols exist, copy them also
    libc_dbg_filepath = f"{libc_filepath}.debug"
    if os.path.isfile(libc_dbg_filepath):
        libc_dbg_proper_filename = utils.get_libc_dbg_proper_filename(libc_filepath)
        libc_dbg_proper_filepath = os.path.join(libs_dirpath, libc_dbg_proper_filename)
        if utils.query_yes_no(
            "Copy:\n"
            f"- {colorama.Style.BRIGHT}{libc_dbg_filepath}{colorama.Style.RESET_ALL}\n"
            f"to {colorama.Style.BRIGHT}{libc_dbg_proper_filepath}{colorama.Style.RESET_ALL}?"
        ):
            shutil.copy2(libc_dbg_filepath, libc_dbg_proper_filepath)
        print()

    # patch the binary to use the new dynamic loader and libc
    patched_binary_filepath = f"{binary_filepath}-{libc_version}"
    if not utils.query_yes_no(
        "Copy:\n"
        f"- {colorama.Style.BRIGHT}{binary_filepath}{colorama.Style.RESET_ALL}\n"
        f"to {colorama.Style.BRIGHT}{patched_binary_filepath}{colorama.Style.RESET_ALL} and patch the latter?"
    ):
        utils.abort()
    shutil.copy2(binary_filepath, patched_binary_filepath)

    ld_basename = os.path.basename(ld_filepath)
    libc_basename = os.path.basename(libc_filepath)
    subprocess.run(
        (
            f"patchelf --set-interpreter ./libs/{shlex.quote(ld_basename)} {shlex.quote(patched_binary_filepath)}"
            f" && patchelf --add-needed ./libs/{shlex.quote(libc_basename)} {shlex.quote(patched_binary_filepath)}"
        ),
        check=True,
        shell=True,
    )


def rebuild():
    with sqlite3.connect(libcs_db_filepath) as conn:
        conn.execute("DROP TABLE IF EXISTS libcs")
        conn.execute(
            "CREATE TABLE libcs"
            "(relpath text, architecture text, distro text, release text, version text, buildID text,"
            "PRIMARY KEY(version, buildID))"
        )

        for filepath in glob.glob(f"{libcs_dirpath}/**/*", recursive=True):
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


# bowkin assumes either the directory `libcs` or a symlink to it can be found
# in the same directory of this script
libcs_dirpath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "libcs")
libcs_db_filepath = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "libcs.db"
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True

    find_parser = subparsers.add_parser("find")
    find_parser.add_argument(
        "symbols",
        type=lambda text: text.split("="),
        nargs="+",
        metavar="symbol=address",
    )

    identify_parser = subparsers.add_parser("identify")
    identify_parser.add_argument("libc", type=argparse.FileType())

    patchelf_parser = subparsers.add_parser("patchelf")
    patchelf_parser.add_argument("binary", type=argparse.FileType())
    patchelf_parser.add_argument("libc", type=argparse.FileType())

    rebuild_parser = subparsers.add_parser("rebuild")

    args = parser.parse_args()

    if args.action == "find":
        for libc in find(args.symbols):
            libc["realpath"] = os.path.realpath(
                os.path.join(libcs_dirpath, libc["relpath"])
            )
            print(json.dumps(libc, sort_keys=True, indent=4))
    elif args.action == "identify":
        for libc in identify(args.libc.name):
            libc["realpath"] = os.path.realpath(
                os.path.join(libcs_dirpath, libc["relpath"])
            )
            print(json.dumps(libc, sort_keys=True, indent=4))
    elif args.action == "patchelf":
        patchelf(args.binary.name, args.libc.name)
    elif args.action == "rebuild":
        rebuild()
