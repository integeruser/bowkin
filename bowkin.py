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


def dump(libc_filepath, symbols):
    print(utils.make_bright("<dump>"))

    with open(libc_filepath, "rb") as f:
        elf = elftools.elf.elffile.ELFFile(f)
        dynsym_section = elf.get_section_by_name(".dynsym")
        for symbol in symbols:
            try:
                libc_symbol = dynsym_section.get_symbol_by_name(symbol)[0]
                libc_offset = libc_symbol.entry.st_value & 0xFFF
            except TypeError:
                pass
            else:
                print(f"{symbol}={hex(libc_offset)}")

    print(utils.make_bright("</dump>"))


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
                    offset = address & 0xFFF
                    try:
                        libc_symbol = dynsym_section.get_symbol_by_name(symbol)[0]
                        libc_offset = libc_symbol.entry.st_value & 0xFFF
                        if libc_offset != offset:
                            break
                    except (IndexError, TypeError):
                        break
                else:
                    utils.dump(dict(libc))
                    matches.append(dict(libc))

    print(utils.make_bright("</find>"))
    return matches


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


def patch(binary_filepath, supplied_libc_filepath):
    print(utils.make_bright("<patch>"))

    binary_dirpath = os.path.dirname(binary_filepath)

    # identify the supplied libc
    matches = identify(supplied_libc_filepath)
    if not matches:
        utils.abort("The supplied libc is not in the local library.")
    # TODO pick the first for now
    libc = matches[0]

    libc_filepath = os.path.join(utils.get_libcs_dirpath(), libc["relpath"])
    libc_architecture = libc["architecture"]
    libc_patch = libc["patch"]
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
    libs_dirpath = os.path.join(
        binary_dirpath, "libs", libc_architecture, libc_version, libc_patch
    )
    ld_proper_filename = f"ld-{libc_version}.so"
    ld_proper_filepath = os.path.join(libs_dirpath, ld_proper_filename)
    libc_proper_filename = f"libc-{libc_version}.so"
    libc_proper_filepath = os.path.join(libs_dirpath, libc_proper_filename)
    if not utils.query_yes_no(
        "Copy:\n"
        f"- {utils.make_bright(ld_filepath)}\n"
        f"- {utils.make_bright(libc_filepath)}\n"
        "to:\n"
        f"- {utils.make_bright(ld_proper_filepath)}\n"
        f"- {utils.make_bright(libc_proper_filepath)}\n"
        "?"
    ):
        utils.abort("Aborted by user.")
    os.makedirs(libs_dirpath, exist_ok=True)
    shutil.copy2(ld_filepath, ld_proper_filepath)
    shutil.copy2(libc_filepath, libc_proper_filepath)

    print()

    # if debug symbols exist, copy them also
    libc_dbg_filepath = f"{libc_filepath}.debug"
    if os.path.isfile(libc_dbg_filepath):
        libs_debug_dirpath = os.path.join(libs_dirpath, ".debug")

        libc_dbg_proper_filename = utils.get_libc_dbg_proper_filename(libc_filepath)
        libc_dbg_proper_filepath = os.path.join(
            libs_debug_dirpath, libc_dbg_proper_filename
        )
        if utils.query_yes_no(
            "Copy:\n"
            f"- {utils.make_bright(libc_dbg_filepath)}\n"
            "to:\n"
            f"- {utils.make_bright(libc_dbg_proper_filepath)}\n"
            "?"
        ):
            os.makedirs(libs_debug_dirpath, exist_ok=True)
            shutil.copy2(libc_dbg_filepath, libc_dbg_proper_filepath)
        print()

    # patch the binary to use the new dynamic loader and libc
    patched_binary_filepath = (
        f"{binary_filepath}-{libc_architecture}-{libc_version}-{libc_patch}"
    )
    if not utils.query_yes_no(
        "Copy:\n"
        f"- {utils.make_bright(binary_filepath)}\n"
        "to:\n"
        f"- {utils.make_bright(patched_binary_filepath)}\n"
        "and patch the latter?"
    ):
        utils.abort("Aborted by user.")
    shutil.copy2(binary_filepath, patched_binary_filepath)

    ld_basename = os.path.basename(ld_proper_filename)
    libc_basename = os.path.basename(libc_proper_filename)
    subprocess.run(
        (
            f"patchelf --set-interpreter {shlex.quote(os.path.relpath(ld_proper_filepath, binary_dirpath))} {shlex.quote(patched_binary_filepath)}"
            f" && patchelf --add-needed {shlex.quote(os.path.relpath(libc_proper_filepath, binary_dirpath))} {shlex.quote(patched_binary_filepath)}"
        ),
        check=True,
        shell=True,
    )

    print(utils.make_bright("</patch>"))


if __name__ == "__main__":

    def _parse_symbol_address_type(text):
        symbol, address = text.split("=")
        address = int(address, 16)
        return (symbol, address)

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")

    dump_parser = subparsers.add_parser(
        "dump", help="Dump symbols offsets of a given libc"
    )
    dump_parser.add_argument("libc", type=argparse.FileType())
    dump_parser.add_argument("symbol", nargs="+")

    find_parser = subparsers.add_parser(
        "find", help="Find which libcs in the local library satisfy symbol=address"
    )
    find_parser.add_argument(
        "symbols", type=_parse_symbol_address_type, nargs="+", metavar="symbol=address"
    )

    identify_parser = subparsers.add_parser(
        "identify",
        help="Identify an unknown libc by searching the local library for libcs with the same buildID",
    )
    identify_parser.add_argument("libc", type=argparse.FileType())

    patch_parser = subparsers.add_parser(
        "patch", help="Patch an ELF binary to use a specific libc"
    )
    patch_parser.add_argument("binary", type=argparse.FileType())
    patch_parser.add_argument("libc", type=argparse.FileType())

    args = parser.parse_args()

    if args.action == "dump":
        dump(args.libc.name, args.symbol)
    elif args.action == "find":
        find(args.symbols)
    elif args.action == "identify":
        identify(args.libc.name)
    elif args.action == "patch":
        patch(args.binary.name, args.libc.name)
    else:
        parser.print_help(sys.stderr)
