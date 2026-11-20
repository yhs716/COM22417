#!/usr/bin/env bash
set -euo pipefail
OML_PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OML_PYTHON="${OML_PYTHON:-python}"
OML_REQUIREMENTS_FILE="${OML_REQUIREMENTS_FILE:-requirements.txt}"
cd -- "$OML_PROJECT_ROOT"
if [[ ! -f "$OML_REQUIREMENTS_FILE" ]]; then
  printf '%s\n' 'Requirements file not found. Check OML_REQUIREMENTS_FILE.' >&2
  exit 1
fi
"$OML_PYTHON" -m pip install --disable-pip-version-check -r "$OML_REQUIREMENTS_FILE" "$@"
"$OML_PYTHON" -m pip check
"$OML_PYTHON" -m compileall -q app.py manage.py backend
