#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

mkdir -p "libcs/arch/pkgs"
cd "libcs/arch/pkgs"
for ARCH in "i686" "x86_64"; do
    wget "https://archive.archlinux.org/packages/g/glibc/" --no-clobber --no-directories --no-parent --recursive --level=1 --execute="robots=off" \
        --accept "glibc-*-$ARCH.pkg.tar.xz" \
        --reject "*.sig"
done

cd "../" && WORKDIR="$(pwd)"
for PKG_FILENAME in pkgs/*.pkg.tar.xz; do
    echo "Processing $PKG_FILENAME..."

    if [[ $PKG_FILENAME =~ glibc-(.*)-$ARCH.pkg.tar.xz ]]; then
        VERS="${BASH_REMATCH[1]}"

        LIBC_FILENAME="libc-$ARCH-$VERS.so"
        LD_FILENAME="ld-$ARCH-$VERS.so"
        if [[ ( ! -f $LIBC_FILENAME ) || ( ! -f $LD_FILENAME ) ]]; then
            pushd . >/dev/null 2>&1
            cd "$(mktemp -d)" && TEMPDIR="$(pwd)"
                if tar xf "$WORKDIR/$PKG_FILENAME"; then
                    mv "$(realpath $(find "$TEMPDIR" -name "libc.so.6"))" "$WORKDIR/$LIBC_FILENAME"
                    mv "$(realpath $(find "$TEMPDIR" -name "ld-*.so"))" "$WORKDIR/$LD_FILENAME"
                fi
            popd >/dev/null 2>&1
        fi
    fi
done
