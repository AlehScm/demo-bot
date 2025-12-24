#!/bin/sh
set -euo pipefail

if [ "$#" -eq 0 ]; then
  set -- python main.py
fi

exec "$@"
