#!/usr/bin/env python3
import re
import shlex
import subprocess


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
