#!/usr/bin/env bash
# UserPromptSubmit hook：每輪一行 FABLE-PROTOCOL 微提醒，並寫 marker 供 e2e 測試驗證觸發
DIR="$(cd "$(dirname "$0")" && pwd)"
date +"%Y-%m-%d %H:%M:%S" > "$DIR/.last_promptsubmit"
echo "🧭 FABLE-PROTOCOL：Observe 先蒐證 → Orient 亮假設；改功能邏輯必附 fail-then-pass 證據；重大結論先抗辯（adversarial-review）再採信。"
