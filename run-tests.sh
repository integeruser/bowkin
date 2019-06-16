#!/usr/bin/env bash
set -e
dirname () { python -c "import os; print(os.path.dirname(os.path.realpath('$0')))"; }
cd "$(dirname "$0")"

bowkin-db rebuild

bowkin-db add data/libc6_2.23-0ubuntu6_amd64.deb
bowkin-db add data/libc6_2.24-11+deb9u4_i386.deb
bowkin-db add data/glibc-2.25-1-i686.pkg.tar.xz

if ! bowkin identify "libcs/libc-amd64-2.23-0ubuntu6.so" | grep "a6f6c7e17083a81da551e3764672e80c39e184d3" 1>/dev/null; then
    exit 1
fi

if ! bowkin dump "libcs/libc-amd64-2.23-0ubuntu6.so" system | grep "0x390" 1>/dev/null; then
    exit 1
fi

if ! bowkin find system=0x390 | grep "a6f6c7e17083a81da551e3764672e80c39e184d3" 1>/dev/null; then
    exit 1
fi

yes | bowkin-db bootstrap

echo "All tests passed!"
