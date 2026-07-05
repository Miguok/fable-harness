#!/usr/bin/env bash
# SessionStart hook：注入 FABLE-PROTOCOL 行為協議，並寫 marker 供 e2e 測試驗證觸發
DIR="$(cd "$(dirname "$0")" && pwd)"
date +"%Y-%m-%d %H:%M:%S" > "$DIR/.last_sessionstart"
cat "$DIR/fable_protocol.md"
