#!/bin/bash
if [ -d ".venv_test" ]; then
    source .venv_test/bin/activate
else
    python3 -m venv .venv_test
    source .venv_test/bin/activate
    pip install requests rich soundfile numpy
fi
python3 tests/full_audit.py