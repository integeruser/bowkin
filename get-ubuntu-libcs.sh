#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

WORKDIR="$(pwd)/libcs/ubuntu"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

for DISTRO in "trusty" "xenial" "artful" "bionic"; do
    pushd . >/dev/null 2>&1
    WORKDIR="$(pwd)/$DISTRO"
    mkdir -p "$WORKDIR"
    cd "$WORKDIR"
        DEB_URLS=""
        for ARCH in "i386" "amd64"; do
            DEB_URLS+=" $(wget -O - "https://packages.ubuntu.com/$DISTRO/$ARCH/libc6/download" 2>/dev/null \
                | grep -o -m 1 "http://[^\"]*libc6[^\"]*.deb")"
        done
        set -- junk $DEB_URLS

        for DEB_URL in $DEB_URLS; do
            DEB_FILENAME="$(basename "$DEB_URL")"
            if [[ $DEB_FILENAME =~ libc6_(.*)_$ARCH.deb ]]; then
                VERS="${BASH_REMATCH[1]}"

                LIBC_FILENAME="libc-$ARCH-$VERS.so"
                LD_FILENAME="ld-$ARCH-$VERS.so"
                if [[ ( ! -f $LIBC_FILENAME ) || ( ! -f $LD_FILENAME ) ]]; then
                    echo "Fetching: "$DEB_FILENAME""

                    pushd . >/dev/null 2>&1
                    TEMPDIR="$(mktemp -d)"
                    cd "$TEMPDIR"
                        wget "$DEB_URL" 2>/dev/null
                        if ar x "$DEB_FILENAME" && tar xf data.tar.?z; then
                            mv "$(realpath $(find "$TEMPDIR" -name "libc.so.6"))" "$WORKDIR/$LIBC_FILENAME"
                            mv "$(realpath $(find "$TEMPDIR" -name "ld-*.so"))" "$WORKDIR/$LD_FILENAME"
                        fi
                    popd >/dev/null 2>&1
                fi
            fi
        done
    popd >/dev/null 2>&1
done
