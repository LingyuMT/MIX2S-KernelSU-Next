#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Polaris build integration, 2026-10-14.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${OUT_DIR:-"$ROOT/out"}
DIST=${DIST_DIR:-"$ROOT/dist"}
JOBS=${JOBS:-2}
[[ "$JOBS" =~ ^[12]$ ]] || { echo 'JOBS must be 1 or 2' >&2; exit 2; }
OUT=$(realpath -m "$OUT")
DIST=$(realpath -m "$DIST")
[[ "$OUT" != "$ROOT" && "$DIST" != "$ROOT" && "$OUT" != "$DIST" ]] || exit 2
for command in make gcc python3 bc bison flex; do command -v "$command" >/dev/null; done
if [[ -z ${TC_PREFIX:-} ]]; then
  bash "$ROOT/build-support/fetch-toolchain.sh"
  TC_PREFIX="$ROOT/.toolchains/aarch64--glibc--stable-2020.02-1/bin/aarch64-linux-"
fi
[[ -x "${TC_PREFIX}gcc" ]] || { echo 'TC_PREFIX must end in aarch64-linux-' >&2; exit 2; }
[[ "$("${TC_PREFIX}gcc" -dumpversion)" == 8.4.0 ]] || { echo 'Use pinned GCC 8.4.0' >&2; exit 2; }
mkdir -p "$OUT" "$DIST"
# Always select the validated config. No non-KSU or moving-branch mode.
cp "$ROOT/build-support/config/polaris_ksu.config" "$OUT/.config"
export KBUILD_BUILD_USER=polaris KBUILD_BUILD_HOST=builder KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='Wed Oct 14 11:51:01 CST 2026'
export LC_ALL=C
args=(-C "$ROOT" O="$OUT" ARCH=arm64 CROSS_COMPILE="$TC_PREFIX"
      CC="${TC_PREFIX}gcc" HOSTCFLAGS=-fcommon LOCALVERSION=
      KSU_VERSION_OVERRIDE=33294 KSU_VERSION_TAG_OVERRIDE=v3.4.0-legacy)
make "${args[@]}" olddefconfig
# KSU includes generated flask.h; complete its producer before parallel build.
nice -n 15 make "${args[@]}" -j"$JOBS" security/selinux/
nice -n 15 make "${args[@]}" -j"$JOBS"
python3 "$ROOT/build-support/verify-build.py" --root "$ROOT" --out "$OUT" --nm "${TC_PREFIX}nm" --report "$DIST/validation.json"
cp "$OUT/arch/arm64/boot/Image.gz-dtb" "$DIST/Image.gz-dtb"
cp "$OUT/Module.symvers" "$DIST/Module.symvers"
cp "$OUT/.config" "$DIST/kernel.config"
cp "$ROOT/build-support/provenance.json" "$DIST/provenance.json"
cp "$ROOT/COPYING" "$DIST/COPYING"
python3 "$ROOT/build-support/build-manifest.py" "$ROOT" "$DIST"
(cd "$DIST"; sha256sum Image.gz-dtb Module.symvers kernel.config > SHA256SUMS)
echo "KSU-only build and validation complete: $DIST"
