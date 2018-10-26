#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys

import elftools.elf.elffile

import utils


def identify(libc_filepath):
    print(utils.make_bright("<identify>"))

    matches = []
    with sqlite3.connect(utils.get_libcs_db_filepath()) as conn:
        conn.row_factory = sqlite3.Row
        matches = [
            dict(libc)
            for libc in conn.execute(
                "SELECT * FROM libcs where buildID=?",
                (utils.extract_buildID_from_file(libc_filepath),),
            )
        ]

    for libc in matches:
        utils.dump(libc)

    print(utils.make_bright("</identify>"))
    return matches


def find(symbols):
    print(utils.make_bright("<find>"))

    matches = []
    with sqlite3.connect(utils.get_libcs_db_filepath()) as conn:
        conn.row_factory = sqlite3.Row
        for libc in conn.execute("SELECT * FROM libcs"):
            libc_filepath = os.path.join(utils.get_libcs_dirpath(), libc["relpath"])
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

    for libc in matches:
        utils.dump(libc)

    print(utils.make_bright("</find>"))
    return matches


def patch(binary_filepath, supplied_libc_filepath):
    print(utils.make_bright("<patch>"))

    binary_dirpath = os.path.dirname(binary_filepath)

    # identify the supplied libc
    matches = identify(supplied_libc_filepath)
    if not matches:
        utils.abort("The supplied libc is not in the database.")
    # TODO pick the first for now
    libc = matches[0]

    libc_filepath = os.path.join(utils.get_libcs_dirpath(), libc["relpath"])
    libc_version = libc["version"]

    ld_filepath = os.path.join(
        os.path.dirname(libc_filepath),
        os.path.basename(libc_filepath).replace("libc-", "ld-"),
    )
    # if the dynamic loader does not exist, abort (don't care about race conditions)
    if not os.path.isfile(ld_filepath):
        utils.abort(
            "The dynamic loader corresponding to the libc to use cannot be found."
            f" It should reside at {utils.make_bright(ld_filepath)}"
        )

    # copy the dynamic loader and the libc to the directory where the binary is located
    libs_dirpath = os.path.join(binary_dirpath, "libs")
    if not utils.query_yes_no(
        "Copy:\n"
        f"- {utils.make_bright(ld_filepath)}\n"
        f"- {utils.make_bright(libc_filepath)}\n"
        "to:\n"
        f"- {utils.make_bright(libs_dirpath)}/\n"
        "?"
    ):
        utils.abort("Aborted by user.")
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
            f"- {utils.make_bright(libc_dbg_filepath)}"
            "to:\n"
            f"- {utils.make_bright(libc_dbg_proper_filepath)}"
            " (this particular name is required by GDB to add debug symbols automatically)\n"
            "?"
        ):
            shutil.copy2(libc_dbg_filepath, libc_dbg_proper_filepath)
        print()

    # patch the binary to use the new dynamic loader and libc
    patched_binary_filepath = f"{binary_filepath}-{libc_version}"
    if not utils.query_yes_no(
        "Copy:\n"
        f"- {utils.make_bright(binary_filepath)}\n"
        "to:\n"
        f"- {utils.make_bright(patched_binary_filepath)}\n"
        "and patch the latter?"
    ):
        utils.abort("Aborted by user.")
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

    print(utils.make_bright("</patch>"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")

    find_parser = subparsers.add_parser(
        "find", help="Find libcs that satisfy symbol=address"
    )
    find_parser.add_argument(
        "symbols",
        type=lambda text: text.split("="),
        nargs="+",
        metavar="symbol=address",
    )

    identify_parser = subparsers.add_parser(
        "identify", help="Print info about the supplied libc"
    )
    identify_parser.add_argument("libc", type=argparse.FileType())

    patch_parser = subparsers.add_parser(
        "patch", help="Patch the supplied binary to use a specific libc"
    )
    patch_parser.add_argument("binary", type=argparse.FileType())
    patch_parser.add_argument("libc", type=argparse.FileType())

    args = parser.parse_args()

    if args.action == "find":
        find(args.symbols)
    elif args.action == "identify":
        identify(args.libc.name)
    elif args.action == "patch":
        patch(args.binary.name, args.libc.name)
    else:
        parser.print_help()
