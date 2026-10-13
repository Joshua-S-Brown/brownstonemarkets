#!/bin/bash
cd "$(dirname "$0")" || exit 1
if [ ! -x ".venv/bin/python" ]; then
  echo "Create the Python environment first using the Mac setup instructions in README.md."
  read -r -p "Press Return to close..."
  exit 1
fi
.venv/bin/python launch.py
if [ "$?" -ne 0 ]; then
  read -r -p "Press Return to close..."
fi
