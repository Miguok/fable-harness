#!/bin/sh
# wiring_runner.sh — git pre-commit runner for FABLE-PROTOCOL component 4.
#
# Install as a repo's pre-commit hook (or append this block to an existing one):
#     cp <fable-repo>/.claude/hooks/wiring_runner.sh .git/hooks/pre-commit
#     chmod +x .git/hooks/pre-commit
#
# It runs every command listed in `.claude/wiring-guards`, one per line.
# A red guard aborts the commit. `ALLOW_UNWIRED=1 git commit ...` states the
# exception out loud and lets it through.
#
# Why a git hook rather than the PreToolUse hook: this path covers *every*
# committer — an agent's Bash tool, an agent's PowerShell tool, a human's
# terminal, a subagent. The PreToolUse gate only sees one of those, and it
# would have to run the suite inside a hook timeout whose expiry is a silent
# fail-open. Here there is no timeout and no silent skip.
#
# What belongs in .claude/wiring-guards: assertions that a thing is ON AN
# EXECUTION PATH — not that it works. Functional tests do not go here. The list
# must stay in the seconds, because a slow gate gets bypassed, and a bypassed
# gate is not a gate. Full regression stays your responsibility before pushing.

# 宣告檔的位置從**第一個參數**取，不從環境變數。
#
# ⚠ 這裡原本是 `DECL="${WIRING_DECL:-.claude/wiring-guards}"`，一個為了測試而
# 開的環境變數。它是**生產環境的靜默繞道**：實測
# `WIRING_DECL=<內容只有 true 的檔案> git commit` → 守衛一次都沒跑、rc=0、
# commit 成立、沒有任何訊息。比官方認可的 `ALLOW_UNWIRED=1` 還糟——後者至少
# 會印一行留痕。而它在 wiring_gate.py、任何 .md、甚至本檔的檔頭都沒被提過，
# 全 repo 只有一個測試在用（2026-09-06 抗辯實測）。
#
# 改成參數之後，生產環境沒有這個縫：git 呼叫 pre-commit 時不帶參數，
# 想改宣告檔位置的人得自己直接執行這支腳本，那本來就繞得過任何東西。
# 「為了測試而在生產程式碼上開的縫」正是這套工具存在的理由，而它就在自己身上。
DECL="${1:-.claude/wiring-guards}"
[ -f "$DECL" ] || exit 0

wiring_failed=""
guards_run=0

# A declaration that exists but cannot be read makes the loop below run zero
# times, and without this the script would still exit 0 — green while skipping
# every guard, the same silent-skip class as the three holes commented below.
# It routes through the same ALLOW_UNWIRED escape as any other red: a gate with
# no way out is a gate people delete.
if [ ! -r "$DECL" ]; then
    echo "[wiring] RED: cannot read $DECL" >&2
    wiring_failed="1"
fi

# `|| [ -n "$line" ]`: without it, a final line with no trailing newline makes
# `read` return non-zero and the last guard is skipped in silence.
while [ -r "$DECL" ] && IFS= read -r line || [ -n "$line" ]; do
    cmd=$(printf '%s' "$line" | sed 's/^[[:space:]]*//')
    case "$cmd" in ''|'#'*) continue ;; esac
    guards_run=$((guards_run + 1))

    # `</dev/null`: without it `eval` inherits this loop's stdin — the
    # declaration file itself — so one guard that reads stdin swallows every
    # remaining line and those guards never run, silently and green.
    if ! out=$(eval "$cmd" </dev/null 2>&1); then
        wiring_failed="1"
        echo "[wiring] RED: $cmd" >&2
        printf '%s\n' "$out" | tail -20 >&2
    else
        # False-green guard: a pytest command that exits 0 having run nothing
        # (bad path, everything skipped, over-filtered by -k) would otherwise
        # be indistinguishable from a real pass.
        case "$cmd" in
            *pytest*)
                if ! printf '%s' "$out" | grep -qE '[1-9][0-9]* passed'; then
                    wiring_failed="1"
                    echo "[wiring] RED (no test actually passed): $cmd" >&2
                    printf '%s\n' "$out" | tail -10 >&2
                fi
                ;;
        esac
    fi
done < "$DECL"

if [ -z "$wiring_failed" ] && [ "$guards_run" -eq 0 ]; then
    echo "[wiring] RED: $DECL declares no guards — opted in but nothing to run" >&2
    echo "[wiring] Either list a guard or delete the declaration; an empty one" >&2
    echo "[wiring] passes every commit while looking like a gate." >&2
    wiring_failed="1"
fi

if [ -n "$wiring_failed" ]; then
    echo "" >&2
    echo "[wiring] Definition of done: a test that passes but is never wired" >&2
    echo "[wiring] into an execution path does not count as done." >&2
    echo "[wiring] To defer deliberately: ALLOW_UNWIRED=1 git commit ..." >&2
    if [ "${ALLOW_UNWIRED:-}" = "1" ]; then
        echo "[wiring] ALLOW_UNWIRED=1 — unwired state accepted on the record" >&2
    else
        exit 1
    fi
fi
exit 0
