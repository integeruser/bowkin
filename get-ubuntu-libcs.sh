#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

mkdir -p libcs/ubuntu/
cd libcs/ubuntu/

for distro in "trusty" "xenial" "artful" "bionic"; do
    pushd . >/dev/null 2>&1
    mkdir -p $distro
    cd $distro
        WORKDIR=$(pwd)

        LIBC_URL=$(wget -O - "https://packages.ubuntu.com/$distro/amd64/libc6/download" 2>/dev/null | grep -o -m 1 "http://[^\"]*libc6[^\"]*.deb")
        LIBC_DEB_NAME=$(basename $LIBC_URL)
        LIBC_VERS=$(basename $LIBC_URL .deb)
        LIBC_FILENAME="$LIBC_VERS.so"
        LIBC_LD_FILENAME="ld-$LIBC_VERS.so"
        if [[ ! -f $LIBC_FILENAME ]]; then
            wget --tries 1 $LIBC_URL

            pushd . >/dev/null 2>&1
            cd $(mktemp -d)
                TEMPDIR=$(pwd)
                ar x $WORKDIR/$LIBC_DEB_NAME
                tar xf data.tar.?z
                mv $(realpath $(find $TEMPDIR -name "libc.so.6")) "$WORKDIR/$LIBC_FILENAME"
                mv $(realpath $(find $TEMPDIR -name "ld-*.so")) "$WORKDIR/$LIBC_LD_FILENAME"
            popd >/dev/null 2>&1

            rm -f $LIBC_DEB_NAME*
        fi
    popd >/dev/null 2>&1
done
