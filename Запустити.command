#!/bin/sh
entrypoint="$(dirname "$0")/assistant/main.py"
for python in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
    if "$python" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
        exec "$python" -B "$entrypoint"
    fi
done
echo "Для запуску помічника потрібен Python 3.12 або новіший." >&2
exit 1
