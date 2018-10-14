#!/usr/bin/env python3
import argparse
import os
import shlex
import shutil
import subprocess

import colorama
import elftools.elf.elffile

import bowkin


def query_yes_no(question):
    return input("{} (y/[N]) ".format(question)).lower() in ("y", "yes")


def abort(message=None):
    if not message:
        message = "Aborted."
    print(
        f"{colorama.Style.BRIGHT}{colorama.Fore.RED}{message}{colorama.Style.RESET_ALL}"
    )
    raise SystemExit


def get_libc_dbg_proper_filename(libc_filepath):
    with open(libc_filepath, "rb") as f:
        elf = elftools.elf.elffile.ELFFile(f)
        data = elf.get_section_by_name(".gnu_debuglink").data()
        libc_dbg_filename = data[: data.index(b"\0")].decode("ascii")
        return libc_dbg_filename


libcs = bowkin.read_db()

parser = argparse.ArgumentParser()
parser.add_argument("binary", type=argparse.FileType())
parser.add_argument("libc", type=argparse.FileType())
args = parser.parse_args()

binary_filepath = args.binary.name
binary_dirpath = os.path.dirname(binary_filepath)


# identify the supplied libc
libcs_matches = bowkin.identify(args.libc.name, show_matches=False)
if not libcs_matches:
    abort("The supplied libc is not in the database.")
libcs_entry = bowkin.get_entry(libcs_matches)

# TODO do better
libc_filepath = libcs_entry["filepath"]
libc_dbg_filepath = libcs_entry["filepath"].replace("libc-", "libc-dbg-")
libc_version = libcs_entry["version"]
ld_filepath = f"{os.path.dirname(libc_filepath)}/ld-{os.path.basename(libc_filepath).replace('libc-', '')}"


# copy the dynamic loader and the libc to the directory where the binary is located
if not query_yes_no(
    f"Copy {colorama.Style.BRIGHT}{ld_filepath}{colorama.Style.RESET_ALL},"
    f" {colorama.Style.BRIGHT}{libc_filepath}{colorama.Style.RESET_ALL}"
    f"and {colorama.Style.BRIGHT}{libc_dbg_filepath}{colorama.Style.RESET_ALL}"
    f" to {colorama.Style.BRIGHT}{binary_dirpath}{colorama.Style.RESET_ALL}?"
):
    abort()
shutil.copy2(ld_filepath, binary_dirpath)
shutil.copy2(libc_filepath, binary_dirpath)
libc_dbg_proper_filename = get_libc_dbg_proper_filename(libc_filepath)
shutil.copy2(libc_dbg_filepath, os.path.join(binary_dirpath, libc_dbg_proper_filename))


# patch the binary to use the new dynamic loader and libc
patched_binary_filepath = f"{binary_filepath}-{libc_version}"
if not query_yes_no(
    f"Copy {colorama.Style.BRIGHT}{binary_filepath}{colorama.Style.RESET_ALL}"
    f" to {colorama.Style.BRIGHT}{patched_binary_filepath}{colorama.Style.RESET_ALL}"
    f" and patch the latter?"
):
    abort()
shutil.copy2(binary_filepath, patched_binary_filepath)

ld_basename = os.path.basename(ld_filepath)
libc_basename = os.path.basename(libc_filepath)
subprocess.run(
    (
        f"patchelf --set-interpreter ./{shlex.quote(ld_basename)} {shlex.quote(patched_binary_filepath)}"
        f" && patchelf --add-needed ./{shlex.quote(libc_basename)} {shlex.quote(patched_binary_filepath)}"
    ),
    check=True,
    shell=True,
)

print(f"{colorama.Style.BRIGHT}{colorama.Fore.GREEN}Done.{colorama.Style.RESET_ALL}")
