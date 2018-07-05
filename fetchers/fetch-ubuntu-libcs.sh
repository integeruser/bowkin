#!/usr/bin/env bash
set -e

WORKDIR="$(pwd)/libcs/ubuntu"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

for DISTRO in "trusty" "xenial" "artful" "bionic"; do
    for ARCH in "i386" "amd64" "armel" "armhf" "arm64"; do
        pushd . >/dev/null 2>&1
        WORKDIR="$(pwd)/$DISTRO"
        mkdir -p "$WORKDIR"
        cd "$WORKDIR"
            
            DEB_URLS="$(wget -O - "https://packages.ubuntu.com/$DISTRO/$ARCH/libc6/download" 2>/dev/null | grep -o -m 1 "http://[^\"]*libc6[^\"]*.deb" || true)"
            for DEB_URL in $DEB_URLS; do

                DEB_FILENAME="$(basename "$DEB_URL")"    
                if [[ $DEB_FILENAME =~ libc6_(.*)_$ARCH.deb ]]; then
                    VERS="${BASH_REMATCH[1]}"

                    LIBC_FILENAME=$(sed -E 's/[^a-zA-Z0-9_\.\-]/_/g' <<< "libc-$ARCH-$VERS.so")
                    LD_FILENAME=$(sed -E 's/[^a-zA-Z0-9_\.\-]/_/g' <<< "ld-$ARCH-$VERS.so")
                    
                    if [[ ( ! -f $LIBC_FILENAME ) || ( ! -f $LD_FILENAME ) ]]; then
                        echo "Processing: $DEB_FILENAME"

                        pushd . >/dev/null 2>&1
                        TEMPDIR="$(mktemp -d)"
                        cd "$TEMPDIR"
                            wget "$DEB_URL" 2>/dev/null
                            if ar x "$DEB_FILENAME" && tar xf data.tar.?z; then
                                mv "$(realpath $(find "$TEMPDIR" -name "libc.so.6"))" "$WORKDIR/$LIBC_FILENAME"
                                mv "$(realpath $(find "$TEMPDIR" -name "ld-*.so"))" "$WORKDIR/$LD_FILENAME"
                            fi
                        popd >/dev/null 2>&1
                    else
                        echo "Skipping: $DEB_FILENAME"
                    fi
                fi
            done
        popd >/dev/null 2>&1
    done
done
