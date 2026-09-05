# -*- coding: utf-8 -*-
"""PreToolUse wiring gate（FABLE-PROTOCOL 組件 4，opt-in）。

一句話：擋住「守衛寫好了、測試綠了，但它從來不在任何執行路徑上」。

為什麼需要它——`verify_gate.py` 管的是上一階：改了程式碼卻沒跑測試。
本 gate 管下一階：**測試跑了、綠了，但那個東西沒有被接上去。**
已兌現的形態（2026-09-05，同一個 repo 一天內挖出四個）：一支限流器帶著
`WIRING_TODO` 註解活了兩個月、生產路徑呼叫數是 0；一支移除淘汰排程的腳本
因為缺 BOM 從第一天就跑不起來；一道租約守門只擋住兩條重啟路徑中的一條。
共通點是它們**都通過了驗收**——檔案存在、測試綠、DoD 打勾、進了版控，
於是那個缺口從此無人看管。比沒做更糟：沒做的還在待辦清單上。

行為（純 opt-in：未宣告的 repo 不會被擋下任何 commit）：
  repo 沒有 `.claude/wiring-guards`  → 不介入判定，但會掃一次該 repo 有沒有
      「接線型守衛」並留下提示（v1.3.0 起；見 note_unregistered）。
      成本：`git rev-parse` 與 `git ls-files` 各一次，且只在 commit 指令上。
  repo 有宣告檔，則在 `git commit` 前檢查兩件事：
    W1 `--no-verify` / `-n`（含 `-nm` 這種叢集寫法，也含與 `--amend` 併用）→ 擋。
       那是繞過 pre-commit 的唯一入口，且不留痕跡。旗標**只看 `git commit` 那一段**，
       不看整條指令列——否則 `git commit -m x && git log -n 1` 會被當成 --no-verify。
    W2 git 真正會讀的那個 pre-commit（`git rev-parse --git-path`）不存在，
       或存在但**內容不提及宣告檔** → 擋。hooks 目錄不入版控，re-clone 後不會
       自動回來；此時守衛檔全在（它們在 repo 裡）卻一次都不會執行——正是本 gate
       要抓的那個病。用 git 問而不是拼 `.git/hooks/`：worktree／submodule 的
       `.git` 是檔案，拼出來的路徑永不存在（恆擋）；設了 core.hooksPath 時
       拼出來的路徑存在但 git 不讀（假綠）。兩個方向都錯過。

W2 刻意不去比對「版控裡的模板副本」：那需要猜每個 repo 把模板放哪，
而猜錯的方向是**靜默放行**。改問「裝好的那份會不會跑宣告檔」，
與專案結構無關，且直接就是接線本身。

判定一律走「剝掉 commit 訊息內文」的版本。2026-09-05 實測：拿整條指令字串
比對時，`git commit -m "禁止用 --amend"` 會讓整道閘靜默放行——而寫這套機制的
那次 commit，訊息裡正好有這個詞。

⚠ **本層是盡力而為，不是執行層**（既有決議見 `wiring_runner.sh` 檔頭）：它讀的是
指令字串，而「這條指令會不會跳過 hook」無法只靠讀字串完全判定。經 `eval`／`sh -c`／
`xargs`／`Start-Process`／git alias 送出的 commit，本層看不到；在字串裡引用
`git commit --no-verify` 當說明文字則會被誤擋。真正擋得住每一個提交者的是
`wiring_runner.sh`——那是 git 自己執行的 pre-commit，換寫法繞不過。

介面：stdin 收 hook JSON（tool_name / tool_input.command）；
      stdout 輸出 deny JSON 或無輸出。任何解析錯誤一律 fail-open
      （exit 0 無輸出）——gate 絕不可弄壞 session。
測試：tests/test_wiring_gate.py（fail-then-pass + 突變已驗證）。
"""
import json
import os
import re
import subprocess
import sys

DECL_REL = os.path.join(".claude", "wiring-guards")

# `git commit` 本體。允許 env 前綴（`FOO=1 git commit`）、`command`/`time` 包裝、
# `git -C <path>` 與 `git -c k=v` 全域旗標；前導界定字元涵蓋 `&&`、`;`、管線、`(`、`{`
# 與**換行**。換行原本不在此列：`git add -A` 換行接 `git commit --no-verify` 因此
# 完全不被判定（整道閘失效），而多行 shell 正是最常見的形態。2026-09-05 實測。
# git 的全域選項不只 `-c`／`-C`：`--no-pager`、`--git-dir=…`、`--work-tree=…`
# 都可以插在 `git` 與 `commit` 之間，而它們原本讓整個樣式比不中——
# `git --no-pager commit -n` 因此完全不被檢查。引號路徑同理（Windows 常態）。
VALUE = r"(?:\"[^\"]*\"|'[^']*'|\S+)"
GIT_GLOBAL_OPT = r"(?:-[cC]\s+" + VALUE + r"|--[\w-]+(?:=" + VALUE + r")?)"
GIT_COMMIT_RE = re.compile(
    r"(?:^|[;&|(){\n\r]|\bthen\b|\bdo\b)\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:command\s+|time\s+)?"
    r"git(?:\.exe)?((?:\s+" + GIT_GLOBAL_OPT + r")*)"
    r"\s+commit(?:\s|$)"
)
AMEND_RE = re.compile(r"(?:^|\s)--amend(?:\s|$)")

# 吃「緊接其後的值」的短旗標：`-Sjohn`、`-CHEAD`、`-mmsg`。掃到它就停——
# 後面那些字母是值，不是旗標。少了這條，`git commit -Sjohn` 會因為值裡有 n
# 而被誤判成 --no-verify（誤擋比漏擋更糟，會讓人把整道閘關掉）。
VALUE_TAKING_SHORT_FLAGS = set("SCcFmtu")

# 一條指令列裡 `git commit` 之後還有別的命令，而它們的旗標不歸這道閘管。
# 2026-09-05 實測：`git commit -m "x" && git log -n 1`、`... ; sort -n f`
# 都被判成 --no-verify 而擋下——比漏擋更糟，因為它擋的是完全正常的用法。
SEGMENT_END_RE = re.compile(r"&&|\|\||[;|\n]")

# commit 訊息內文：`-m`/`-F`/`--message` 的值與 heredoc 主體。
# 短旗標那一條保留叢集裡的其他字母（`-nm "x"` → `-n `），否則剝掉訊息時
# 會連 `-n` 一起剝掉，變成用訊息旗標就能繞過整道閘。
STRIP_PATTERNS = [
    (re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?^\s*\2\s*$", re.S | re.M), " "),
    (re.compile(r'(-[A-Za-z]*)[mF]\s+"(?:[^"\\]|\\.)*"'), r"\1 "),
    (re.compile(r"(-[A-Za-z]*)[mF]\s+'[^']*'"), r"\1 "),
    (re.compile(r"(-[A-Za-z]*)[mF]\s+\S+"), r"\1 "),
    (re.compile(r'--(?:message|file)(?:=|\s+)"(?:[^"\\]|\\.)*"'), " "),
    (re.compile(r"--(?:message|file)(?:=|\s+)'[^']*'"), " "),
    (re.compile(r"--(?:message|file)(?:=|\s+)\S+"), " "),
]

W1_REASON = """This commit uses --no-verify (fable wiring_gate).

--no-verify skips the repo's pre-commit hook — which is where the wiring guards
listed in .claude/wiring-guards actually run. Skipping it leaves no trace in git
history, so nobody downstream can tell this commit was never checked.

Definition of done: a test that passes but is never wired into an execution path
does not count as done.

Pick one:
  1. Drop --no-verify and let the guards run.
  2. A guard is genuinely red and you must defer → ALLOW_UNWIRED=1 git commit ...
     (keeps the hook: it prints which guard is red, then lets the commit through,
     leaving the trace in your terminal and in the commit message).
  3. The guard itself is broken → fix the guard (and prove by mutation that it
     flips), rather than going around it."""


def strip_message_bodies(command):
    """Blank out commit message bodies so only the real command remains."""
    out = command
    for pat, repl in STRIP_PATTERNS:
        out = pat.sub(repl, out)
    return out


def commit_invocations(stripped):
    """`[(global options, argument segment)]` for every `git commit` on the line.

    The options travel with their own invocation. Read from the whole line
    instead, a leading `git -C /other status && git commit …` pointed the whole
    check at /other and switched the gate off.
    """
    out = []
    for m in GIT_COMMIT_RE.finditer(stripped):
        rest = stripped[m.end():]
        end = SEGMENT_END_RE.search(rest)
        out.append((m.group(1) or "", rest[:end.start()] if end else rest))
    return out


def commit_segments(stripped):
    """Every `git commit …` argument segment on the line, in order.

    All of them, because both halves are real mistakes. Reading the whole line
    as one flag pool made `git commit -m "x" && git log -n 1` look like
    `--no-verify` — a false deny on an ordinary shape, which is worse than a
    miss: a gate that fires on normal work gets switched off. Reading only the
    first segment has the opposite failure: `git commit -m "x" && git commit -n`
    would pass while the second commit skips the hook.
    """
    return [seg for _, seg in commit_invocations(stripped)]


GIT_C_RE = re.compile(r"-C\s+(" + VALUE + r")")
GIT_CONFIG_RE = re.compile(r"-c\s+(" + VALUE + r")")
# 續行的寫法**依 shell 而異**，不能兩種都認：bash 的行尾反引號是命令替換
# （`` TAG=`git describe` ``），把它當續行會把下一行併上來、讓 `git` 前面失去
# 分隔符，反而製造一個放行漏洞。工具名已經告訴我們是哪個 shell，就照它分。
CONTINUATION_RE = {
    "Bash": re.compile(r"\\\r?\n"),
    "PowerShell": re.compile(r"`\r?\n"),
}


def inline_config(options):
    """`-c k=v` from *this* invocation, as arguments for our own git call.

    `git -c core.hooksPath=/dev/null commit` points git at a hooks directory
    that has no pre-commit — a one-shot bypass that leaves no configuration
    behind. Asking git where hooks live *without* passing the same `-c` gives
    the answer for a different configuration than the one about to run.
    """
    args = []
    for pair in GIT_CONFIG_RE.findall(options):
        args += ["-c", pair.strip("\"'")]
    return args


def target_dir(options):
    """The directory this commit acts on: `git -C <path> commit` targets <path>.

    Read from this invocation's own options. Taken from the whole line, a
    leading `git -C /other status && git commit …` aimed the check at /other,
    where there is no declaration — switching the gate off entirely.
    """
    m = GIT_C_RE.search(options)
    return m.group(1).strip("\"'") if m else None


# git 接受長旗標的唯一前綴縮寫，而 `--no-verb…`（verbose）與 `--no-veri…`
# 的共同前綴到 `--no-ver` 為止——再長一個字元就只可能是 --no-verify。
NO_VERIFY_LONG = re.compile(r"^--no-veri(?:f(?:y)?)?$")


def skips_the_hook(segment):
    """True when this `git commit …` segment would skip the pre-commit hook.

    Short flags cluster (`-nm` *is* `-n -m`), so the scan walks the letters of
    each token rather than matching `-n` as a whole word. It stops at the first
    value-taking flag, because everything after it is that flag's value. Quotes
    come off first: git reads `"-n"` as the flag, and a token-level string
    comparison did not.
    """
    for raw in segment.split():
        token = raw.strip("\"'")
        if NO_VERIFY_LONG.match(token):
            return True
        if token == "--":
            break  # everything after this is a path, not a flag
        if token.startswith("--") or not token.startswith("-") or len(token) < 2:
            continue
        for ch in token[1:]:
            if ch == "n":
                return True
            if ch in VALUE_TAKING_SHORT_FLAGS:
                break
    return False


def normalised(payload):
    """The command with continuations joined and message bodies blanked out."""
    command = (payload.get("tool_input") or {}).get("command") or ""
    joiner = CONTINUATION_RE.get(payload.get("tool_name"))
    return strip_message_bodies(joiner.sub(" ", command) if joiner else command)


def classify(payload):
    """Return 'SKIP', 'NOVERIFY' or 'COMMIT' for one PreToolUse payload."""
    if payload.get("tool_name") not in ("Bash", "PowerShell"):
        return "SKIP"
    segments = commit_segments(normalised(payload))
    if not segments:
        return "SKIP"
    # --no-verify is checked BEFORE --amend: `git commit --amend --no-verify`
    # skips the hook exactly like a plain --no-verify does, and testing amend
    # first let that shape through as an untraceable bypass.
    if any(skips_the_hook(s) for s in segments):
        return "NOVERIFY"
    if all(AMEND_RE.search(s) for s in segments):
        return "SKIP"
    return "COMMIT"


def repo_root(cwd=None):
    """Absolute path of the enclosing git work tree, or None."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=5, cwd=cwd,
        )
    except Exception:
        return None
    root = out.stdout.strip()
    return root if out.returncode == 0 and root else None


def precommit_path(root, config_args=()):
    """Where git will actually look for the pre-commit hook, or None.

    Not ``<root>/.git/hooks/pre-commit``: in a worktree or a submodule ``.git``
    is a *file*, so that path never exists and every commit was denied with a
    remedy (``cp … .git/hooks/pre-commit``) that cannot work there. The reverse
    error is just as real — with ``core.hooksPath`` set (husky, lefthook) that
    path can exist while git reads a different one, which would pass a repo
    whose guards never run. ``git rev-parse --git-path`` answers both.
    """
    try:
        out = subprocess.run(
            ["git", *config_args, "rev-parse", "--git-path", "hooks/pre-commit"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=5, cwd=root,
        )
    except Exception:
        return None
    path = out.stdout.strip()
    if out.returncode != 0 or not path:
        return None
    return path if os.path.isabs(path) else os.path.join(root, path)


# 接線型守衛的形狀：檔名同時帶「測試」與「接線」兩種詞。掃檔名而不是內容，
# 因為這只是提示，代價必須接近零。
GUARD_FILE_RE = re.compile(
    r"(^|/)[^/]*(test|spec)[^/]*(wired|wiring|single_source|_gate|gated)[^/]*"
    r"\.(py|ts|js|sh)$", re.I)
# FABLE_STATE_DIR 只為測試而存在：提示檔寫在使用者真正的 ~/.claude/state，
# 測試不得碰它。
NOTE_DIR = os.environ.get(
    "FABLE_STATE_DIR", os.path.join(os.path.expanduser("~"), ".claude", "state"))


def note_unregistered(root, declared):
    """Leave a note when a repo has wiring-shaped guards but no declaration.

    The gate is opt-in, and opt-in has a matching failure: it does nothing in
    every repo nobody remembered to opt in. So when a repo looks like it
    *already writes* this kind of guard, say so once — as a note on disk, read
    and injected by the SessionStart hook.

    It is a note rather than a message from here because a PreToolUse hook has
    no way to say anything without also blocking: `permissionDecision: allow`
    discards its reason, and stderr on exit 0 is thrown away. A hint that never
    reaches anyone is the same disease this gate exists to catch.
    """
    # 逐**位元組**替換，因為讀這個檔名的是 inject_protocol.sh 的
    # `tr -c 'A-Za-z0-9' '_'`，而 tr 是逐位元組的。Python 逐字元的話，
    # 路徑含非 ASCII（中文／日文／韓文目錄）時兩端算出來的檔名不同：
    # 提示寫得出來、卻永遠讀不到——正是 1.3.0 自稱修掉的那個病。
    safe = re.sub(rb"[^A-Za-z0-9]", b"_", root.encode("utf-8")).decode("ascii")
    note = os.path.join(NOTE_DIR, "wiring_unregistered_%s.txt" % safe)
    if declared:
        # 宣告檔補上了就把提示收掉，否則它會永遠掛在每次 session 開場
        try:
            os.remove(note)
        except OSError:
            pass
        return
    try:
        # `-z`：不加的話 git 會把非 ASCII 檔名轉成八進位跳脫
        # （`"tests/test_\346\270\254..."`），提示對目標讀者變成亂碼。
        out = subprocess.run(["git", "ls-files", "-z"], capture_output=True,
                             encoding="utf-8", errors="replace", timeout=5, cwd=root)
        # 長度在**寫入端**截，而且以字元為單位。交給 shell 的 `cut -c` 截會切在
        # 多位元組字元中間——GNU coreutils 的 `-c` 是逐位元組的，
        # 而「位元組 vs 字元」正是這一批要修的那個病。
        found = [f[:120] for f in out.stdout.split("\0") if GUARD_FILE_RE.search(f)][:8]
        if not found:
            return
        os.makedirs(NOTE_DIR, exist_ok=True)
        with open(note, "w", encoding="utf-8", newline="") as fh:
            fh.write("repo: %s\n" % root)
            fh.write("\n".join(found) + "\n")
    except (OSError, subprocess.SubprocessError):
        return  # 提示失敗絕不影響 commit


def check_wiring(root, config_args=()):
    """Return a deny reason, or None when the repo's guards are properly wired."""
    decl = os.path.join(root, DECL_REL)
    if not os.path.isfile(decl):
        return None  # repo has not opted in — do nothing at all

    installed = precommit_path(root, config_args)
    if installed is None:
        return None  # cannot ask git where hooks live → fail open, never guess
    if not os.path.isfile(installed):
        return (
            "This repo declares wiring guards but has no pre-commit hook "
            "(fable wiring_gate).\n\n"
            "  declared: %s\n"
            "  missing : %s\n\n"
            "The hooks directory is not version controlled, so it does not come back "
            "after a re-clone. Right now every guard file is present in the repo and not "
            "one of them will ever run — the exact failure this gate exists to catch.\n\n"
            "Install the runner shipped with this kit at exactly that path:\n"
            "  cp <fable-repo>/.claude/hooks/wiring_runner.sh %s\n"
            "  chmod +x %s" % (DECL_REL, installed, installed, installed)
        )

    try:
        with open(installed, "r", encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    except OSError:
        return None  # unreadable → fail open, never break the session

    if "wiring-guards" not in body:
        return (
            "The installed pre-commit hook never runs the wiring guards "
            "(fable wiring_gate).\n\n"
            "  declared: %s\n"
            "  installed: %s (no reference to the declaration)\n\n"
            "The guards exist and pass, but nothing invokes them on commit. A guard that "
            "only runs when somebody remembers to run it is not a gate.\n\n"
            "Either append the runner block from "
            "<fable-repo>/.claude/hooks/wiring_runner.sh to your existing pre-commit, "
            "or install that file as the hook if you have none of your own."
            % (DECL_REL, installed)
        )
    return None


def deny(reason):
    """Emit the PreToolUse deny envelope."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def main(argv=None):
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail-open: a gate must never break the session

    try:
        verdict = classify(payload)
        if verdict == "SKIP":
            return 0
        invocations = commit_invocations(normalised(payload))
        options = invocations[0][0] if invocations else ""
        root = repo_root(cwd=target_dir(options))
        if not root:
            return 0
        declared = os.path.isfile(os.path.join(root, DECL_REL))
        note_unregistered(root, declared)
        # W1 only applies to repos that opted in, so an unrelated repo using
        # --no-verify is none of this gate's business.
        if not declared:
            return 0
        if verdict == "NOVERIFY":
            deny(W1_REASON)
            return 0
        reason = check_wiring(root, inline_config(options))
        if reason:
            deny(reason)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
