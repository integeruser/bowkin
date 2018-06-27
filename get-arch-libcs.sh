#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

mkdir -p libcs/arch/
cd libcs/arch/
WORKDIR=$(pwd)

wget "https://archive.archlinux.org/packages/g/glibc/" --no-clobber --no-directories --no-parent --recursive --level=1 --execute=robots=off \
    --accept "glibc-*-x86_64.pkg.tar.xz" \
    --reject "*.sig*"

for LIBC_PKG_NAME in *.pkg.tar.xz; do
    echo $LIBC_PKG_NAME

    LIBC_VERS=$(basename $LIBC_PKG_NAME .pkg.tar.xz)
    LIBC_FILENAME="$LIBC_VERS.so"
    LIBC_LD_FILENAME="ld-$LIBC_VERS.so"
    if [[ ! -f $LIBC_FILENAME ]]; then
        pushd . >/dev/null 2>&1
        cd $(mktemp -d)
            TEMPDIR=$(pwd)
            tar xf $WORKDIR/$LIBC_PKG_NAME
            mv $(realpath $(find $TEMPDIR -name "libc.so.6")) "$WORKDIR/$LIBC_FILENAME"
            mv $(realpath $(find $TEMPDIR -name "ld-*.so")) "$WORKDIR/$LIBC_LD_FILENAME"
        popd >/dev/null 2>&1
    fi

    rm -f $LIBC_PKG_NAME
done
