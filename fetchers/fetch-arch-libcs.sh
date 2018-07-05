#!/usr/bin/env bash
set -e

WORKDIR="$(pwd)/libcs/arch"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

PKG_URLS=""
for ARCH in "i686" "x86_64"; do
    PKG_URLS="$PKG_URLS $(wget "https://archive.archlinux.org/packages/g/glibc/" 2>&1 \
        --spider --no-clobber --no-directories --no-parent --recursive --level=1 --execute="robots=off" \
        --accept "glibc-*-$ARCH.pkg.tar.xz" --reject "*.sig" \
        | grep -Eo http.+\.pkg\.tar\.xz || true)"
done
set -- junk $PKG_URLS

for PKG_URL in $PKG_URLS; do
    PKG_FILENAME="$(basename "$PKG_URL")"
    if [[ $PKG_FILENAME =~ glibc-(.*)-$ARCH.pkg.tar.xz ]]; then
        VERS="${BASH_REMATCH[1]}"

        LIBC_FILENAME=$(sed -E 's/[^a-zA-Z0-9_\.\-]/_/g' <<< "libc-$ARCH-$VERS.so")
        LD_FILENAME=$(sed -E 's/[^a-zA-Z0-9_\.\-]/_/g' <<< "ld-$ARCH-$VERS.so")
        
        if [[ ( ! -f $LIBC_FILENAME ) || ( ! -f $LD_FILENAME ) ]]; then
            echo "Processing: "$PKG_FILENAME""

            pushd . >/dev/null 2>&1
            TEMPDIR="$(mktemp -d)"
            cd "$TEMPDIR"
                wget "$PKG_URL" 2>/dev/null
                if tar xf "$PKG_FILENAME"; then
                    mv "$(realpath $(find "$TEMPDIR" -name "libc.so.6"))" "$WORKDIR/$LIBC_FILENAME"
                    mv "$(realpath $(find "$TEMPDIR" -name "ld-*.so"))" "$WORKDIR/$LD_FILENAME"
                fi
            popd >/dev/null 2>&1
        else
            echo "Skipping: $PKG_FILENAME"
        fi
    fi
done
