#!/usr/bin/env bash
set -euo pipefail
OML_PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OML_PYTHON="${OML_PYTHON:-python}"
cd -- "$OML_PROJECT_ROOT"
exec "$OML_PYTHON" -m backend.hosting "$@"
