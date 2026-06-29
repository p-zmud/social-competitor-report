#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
for pidfile in "$DIR/.backend.pid" "$DIR/.frontend.pid"; do
    if [ -f "$pidfile" ]; then
        kill "$(cat "$pidfile")" 2>/dev/null
        rm "$pidfile"
    fi
done
echo "Dashboard stopped."
