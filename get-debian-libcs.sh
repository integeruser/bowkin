#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

mkdir -p "libcs/debian"
cd "libcs/debian"

for DISTRO in "jessie" "wheezy" "stretch"; do
    pushd . >/dev/null 2>&1
    mkdir -p "$DISTRO"
    cd "$DISTRO"

        mkdir -p "pkgs"
        cd "pkgs"
        for ARCH in "i386" "amd64"; do
            DEB_URL="$(wget -O - "https://packages.debian.org/$DISTRO/$ARCH/libc6/download" 2>/dev/null | grep -o -m 1 "http://[^\"]*libc6[^\"]*.deb")"
            DEB_FILENAME="$(basename "$DEB_URL")"
            if [[ ! -f "$DEB_FILENAME" ]]; then
                wget --tries 1 "$DEB_URL"
            fi
        done

        cd "../" && WORKDIR="$(pwd)"
        for ARCH in "i386" "amd64"; do
            for DEB_FILENAME in pkgs/*.deb; do
                echo "Processing $DEB_FILENAME..."

                if [[ $DEB_FILENAME =~ libc6_(.*)_$ARCH.deb ]]; then
                    VERS="${BASH_REMATCH[1]}"

                    LIBC_FILENAME="libc-$ARCH-$VERS.so"
                    LD_FILENAME="ld-$ARCH-$VERS.so"
                    if [[ ( ! -f $LIBC_FILENAME ) || ( ! -f $LD_FILENAME ) ]]; then
                        pushd . >/dev/null 2>&1
                        cd "$(mktemp -d)" && TEMPDIR="$(pwd)"
                            if ar x "$WORKDIR/$DEB_FILENAME" && tar xf data.tar.?z; then
                                mv "$(realpath $(find "$TEMPDIR" -name "libc.so.6"))" "$WORKDIR/$LIBC_FILENAME"
                                mv "$(realpath $(find "$TEMPDIR" -name "ld-*.so"))" "$WORKDIR/$LD_FILENAME"
                            fi
                        popd >/dev/null 2>&1
                    fi
                fi
            done
        done
    popd >/dev/null 2>&1
done
