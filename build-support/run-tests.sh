#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python3 "$ROOT/build-support/tests/test-allowlist.py"
python3 "$ROOT/build-support/tests/test-keyring.py"
