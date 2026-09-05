#!/usr/bin/env bash
# SessionStart hook：注入 FABLE-PROTOCOL 行為協議，並寫 marker 供 e2e 測試驗證觸發
DIR="$(cd "$(dirname "$0")" && pwd)"
date +"%Y-%m-%d %H:%M:%S" > "$DIR/.last_sessionstart"
cat "$DIR/fable_protocol.md"

# 接線關卡留下的提示：這個 repo 已經在寫接線型守衛，卻沒有宣告檔。
# 提示走這條路而不是 PreToolUse 自己說，是因為 PreToolUse 沒有「不擋人又能說話」
# 的輸出（allow 會丟掉理由、exit 0 的 stderr 被丟棄）；SessionStart 的輸出才會進上下文。
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -n "$ROOT" ]; then
    SAFE=$(printf '%s' "$ROOT" | tr -c 'A-Za-z0-9' '_')
    NOTE="$HOME/.claude/state/wiring_unregistered_$SAFE.txt"
    if [ -f "$NOTE" ]; then
        echo ""
        echo "## 接線關卡：這個 repo 尚未 opt-in"
        echo ""
        echo "掃到以下疑似「斷言某個東西在執行路徑上」的守衛，但沒有 \`.claude/wiring-guards\`——"
        echo "也就是說它們現在不會在 commit 時被執行："
        echo ""
        sed -n '2,$p' "$NOTE" | sed 's/^/  - /'
        echo ""
        echo "要接上：把要跑的守衛逐行寫進 \`.claude/wiring-guards\`，並把"
        echo "\`$DIR/wiring_runner.sh\` 複製成該 repo 的 \`.git/hooks/pre-commit\`（見 INSTALL.md 步驟 10）。"
        echo "不需要就刪掉這個提示檔：\`$NOTE\`"
    fi
fi
