#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
NAME=aarch64--glibc--stable-2020.02-1
SHA=afc6cb199a68992aed685861cb1e43d647bcaef63fea93d44e20e0e26623fd88
CACHE="$ROOT/.toolchains"
mkdir -p "$CACHE"
ARCHIVE="$CACHE/$NAME.tar.bz2"
if [[ ! -f "$ARCHIVE" ]]; then
  curl --fail --location --retry 3 --proto '=https' --tlsv1.2 \
    "https://toolchains.bootlin.com/downloads/releases/toolchains/aarch64/tarballs/$NAME.tar.bz2" -o "$ARCHIVE.partial"
  mv "$ARCHIVE.partial" "$ARCHIVE"
fi
echo "$SHA  $ARCHIVE" | sha256sum --check --status
if [[ ! -x "$CACHE/$NAME/bin/aarch64-linux-gcc" ]]; then
  tar -xjf "$ARCHIVE" -C "$CACHE"
fi
"$CACHE/$NAME/bin/aarch64-linux-gcc" -dumpversion
