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
`wiring_runner.sh`——那是 git 自己執行的 pre-commit。

⚠ **但「繞不過」是過度宣稱，2026-09-06 外部審查實測推翻。** git 的 `core.hooksPath`
可以指到別處，而它至少有四條 transient config 通道可設：`-c`、
`GIT_CONFIG_COUNT/KEY_n/VALUE_n`、`--config-env=`、`GIT_CONFIG_PARAMETERS`。
實測 `git --config-env=core.hooksPath=<空目錄> commit`：守衛一次都沒跑、
**commit rc=0 成功**，而當時的 gate 回 allow。

誠實的宣稱是：**git 用 repo 自己的 hook path 時，每一次 commit 都會經過 runner；
而這道 PreToolUse 另外偵測常見的 runtime override，偵測不到的就擋（fail-closed）。**
真要做到「提交者繞不過」，enforcement 必須移到 server 端（分支保護／CI），
那不在本套件的範圍內。

這一課比那兩條繞道本身重要：**只要一道閘的正確性取決於外部系統的實際狀態，
就不能拿「我列得出來的幾種輸入語法」當成契約。** 前三輪抗辯各自栽在同一個
形狀上——prompt 的形狀、測試指令的語法、淘汰的情境——這是第四次。

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

QUIET_PER_LABEL = 20   # 同一個標籤最多幾行


def note_quiet(label, exc=None):
    """把一次「閘判不出來／自己壞掉」寫成一行，落在同目錄的 `.gate_fail`。

    這是本套件收斂的關鍵：**fail-open 沒問題，安靜的 fail-open 才是問題。**
    三道閘的每一條 fail-open 在外部看起來都和「一切正常」一模一樣，於是它們
    可以壞掉好幾天、跨好幾個版本而沒有人發現——2026-09-06 一輪抗辯找出 26 條
    缺陷，其中約一半是這個形態，而且它是唯一一個「不修就會一直被重新發現」的
    類別：其他類別修完就結案，安靜的分支可以無限新增。

    契約（三支 hook 各有一份，由 tests/test_no_silent_gate.py 綁在一起）：
      - 絕不拋例外——遙測自己壞掉不得破壞 fail-open
      - 一次一行：UTC 時間戳、呼叫點標籤、例外類別
      - **只寫標籤與例外類別，不寫 payload**。格式化在這裡做而不是交給呼叫端：
        第一版簽名是 `note_quiet(reason)`，於是這條不變式散在 16 個呼叫點各自
        遵守，而當場就有 2 個沒遵守（一個用 %r 印環境變數的值、一個寫
        `str(exc)`，而 OSError 會帶路徑）。這個檔案的內容會被注入回對話。
      - 同一個標籤最多 `QUIET_PER_LABEL` 行。**刻意沒有全域上限**：三支寫的是
        同一個檔，全域預算等於共用，實測一支壞掉灌滿 500 行之後，另外兩支的
        失效永遠寫不進去且無人知道——那正是這個機制要治的病，被治療複製了
        一份（2026-09-06 抗辯，simplifier 鏡頭指出，我實測重現）。
        逐標籤之後成長仍有界（標籤數 × 20），而新的標籤永遠進得去。
    """
    try:
        from datetime import datetime, timezone
        marker = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gate_fail")
        text = "%s: %s" % (" ".join(str(label).split())[:120],
                           type(exc).__name__ if exc is not None else "-")
        seen = 0
        if os.path.exists(marker):
            with open(marker, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.rstrip("\r\n").endswith(text):
                        seen += 1
        if seen >= QUIET_PER_LABEL:
            return
        with open(marker, "a", encoding="utf-8") as fh:
            fh.write("%s %s\n" % (datetime.now(timezone.utc).isoformat(), text))
    except Exception:  # quiet-ok: 遙測自身故障不得破壞 fail-open，這裡沒有第二個出口
        pass


DECL_REL = os.path.join(".claude", "wiring-guards")

# `git commit` 本體。允許 env 前綴（`FOO=1 git commit`）、`command`/`time` 包裝、
# `git -C <path>` 與 `git -c k=v` 全域旗標；前導界定字元涵蓋 `&&`、`;`、管線、`(`、`{`
# 與**換行**。換行原本不在此列：`git add -A` 換行接 `git commit --no-verify` 因此
# 完全不被判定（整道閘失效），而多行 shell 正是最常見的形態。2026-09-05 實測。
# git 的全域選項不只 `-c`／`-C`：`--no-pager`、`--git-dir=…`、`--work-tree=…`
# 都可以插在 `git` 與 `commit` 之間，而它們原本讓整個樣式比不中——
# `git --no-pager commit -n` 因此完全不被檢查。引號路徑同理（Windows 常態）。
VALUE = r"(?:\"[^\"]*\"|'[^']*'|\S+)"
# git 的全域長選項有一批是**吃下一個 token 當值**的（`--git-dir <path>`）。
# 原本只認 `--opt=value`，於是 `git --git-dir /alt/.git commit` 整條樣式比不中
# ——不是放行，是**根本沒被認成 commit**，整道閘完全不介入。實測那條指令
# 讓守衛不跑而 commit 成立，gate 一聲不吭。`=` 的寫法擋得住、空格的擋不住，
# 是同一個選項的兩種拼法，屬「同一類沒掃完」。
GIT_VALUE_OPTS = (r"--(?:git-dir|work-tree|namespace|exec-path|super-prefix"
                  r"|attr-source|config-env)")
GIT_GLOBAL_OPT = (r"(?:-[cC]\s+" + VALUE + r"|" + GIT_VALUE_OPTS + r"\s+" + VALUE
                  + r"|--[\w-]+(?:=" + VALUE + r")?)")
# `git` 之前那一段。原本只認「環境變數指派」加 `command`／`time` 兩個包裝器，
# 於是 `env git commit --no-verify`、`sudo git commit --no-verify`、
# `nice git commit --no-verify` 三種寫法**整條樣式比不中**——回的是 SKIP，
# 也就是閘完全不介入，而那三條指令跑起來與裸的 `--no-verify` 一模一樣
# （2026-09-06 抗辯實測三條全 SKIP）。這是「同一件事的多種拼法只掃了一種」，
# 與 `--git-dir` 空格寫法同一類。
#
# 整段用**同一個捕捉群組**吃下來（不是像從前那樣把包裝器排除在群組外），
# 因為 `env GIT_DIR=/x git commit` 的賦值必須進得了 env 前綴：探測子行程
# 少了它就會拿真 repo 的設定去解析一個指向別處的 commit，答錯的方向是放行。
# `ENV_ASSIGN_RE` 只挑得出賦值，`sudo`／`-u root` 這些會被它忽略。
WRAPPER_NAME = (r"(?:command|time|env|sudo|doas|nice|nohup|stdbuf"
                # 這一批 2026-09-06 補上：全部實測讓整條樣式比不中 → SKIP →
                # 無條件放行。`winpty` 在 Git for Windows 是預設安裝的，是
                # 這台機器上最順手的那一個。
                r"|timeout|winpty|setsid|unbuffer|chronic|ionice|strace|busybox)")
# 包裝器後面可以接自己的參數（`timeout 60`、`busybox sh -c`、`strace -f`）。
# 那些參數限定成「不含引號的字詞」並用否定環視擋住 `git`：允許任意 token 的話，
# `echo "git commit is fun"` 會因為引號可以被單獨吃掉而變成一次 commit——
# 那是誤擋，比漏擋更糟。
_WRAP_ARG = r"(?!git(?:\.exe)?(?:\s|$))[-\w./=:+]+"
# 包裝器自己的旗標可以帶一個獨立的值（`sudo -u root`）。那個值同樣用否定環視
# 擋住 `git` 與另一個旗標。
PREFIX_TOKEN = (r"(?:" + WRAPPER_NAME + r"(?:\s+" + _WRAP_ARG + r")*"
                r"|[A-Za-z_][A-Za-z0-9_]*=" + VALUE +
                r"|-\S+(?:\s+(?!git(?:\.exe)?[\s]|-)[^\s;&|]+)?)")
GIT_COMMIT_RE = re.compile(
    r"(?:^|[;&|(){\n\r]|\bthen\b|\bdo\b)\s*"
    r"((?:" + PREFIX_TOKEN + r"\s+)*)"
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
    # 引號那兩條用 `\s*` 而不是 `\s+`：`git commit -m"訊息"`（`-m` 後不接空白）
    # 是 git 接受的合法寫法，而三條原本都要求空白，於是訊息內文剝不掉——實測
    # `git commit -m"fix: stop suggesting --no-verify"` 被判成 NOVERIFY 而**誤擋**，
    # 同義的 `-m "…"` 正常放行。本檔檔頭記載過同型事故（訊息含 `--amend`），
    # 也逐字寫著誤擋比漏擋更糟（2026-09-06 抗辯實測）。
    # 裸值那條仍要求空白：放寬的話 `-m` 會把後面整個 token 吃掉，`-nm` 這類
    # 叢集寫法的判定會跟著壞掉。
    (re.compile(r'(-[A-Za-z]*)[mF]\s*"(?:[^"\\]|\\.)*"'), r"\1 "),
    (re.compile(r"(-[A-Za-z]*)[mF]\s*'[^']*'"), r"\1 "),
    (re.compile(r"(-[A-Za-z]*)[mF]\s+\S+"), r"\1 "),
    (re.compile(r'--(?:message|file)(?:=|\s+)"(?:[^"\\]|\\.)*"'), " "),
    (re.compile(r"--(?:message|file)(?:=|\s+)'[^']*'"), " "),
    (re.compile(r"--(?:message|file)(?:=|\s+)\S+"), " "),
]

HOOKSPATH_REASON = """This commit sets core.hooksPath and the gate cannot follow it
(fable wiring_gate).

core.hooksPath decides where git looks for pre-commit — which is where the wiring
guards actually run. Point it somewhere else and the guards never execute, with no
trace in git history. Git accepts that value through at least four channels: `-c`,
GIT_CONFIG_COUNT/KEY_n/VALUE_n, `--config-env=`, and GIT_CONFIG_PARAMETERS.

This gate mirrors the ones it can parse into its own probe, so that it asks git the
same question the commit will. When it sees `hooksPath` on the line and cannot
account for it, it stops instead of guessing: it would otherwise report on a
configuration different from the one about to run — a green that means nothing.

Pick one:
  1. Drop the hooksPath override and let the repo's own hooks run.
  2. The guards are genuinely red and you must defer → ALLOW_UNWIRED=1 git commit ...
  3. This is a spelling the gate should understand → open an issue with the exact
     command; enumerating spellings is how this gate got here, so it wants the case."""

UNPARSED_REASON = """This looks like a commit the gate could not parse (fable wiring_gate).

The command has a bare `git … commit` on it, and it also carries either a flag
that skips the pre-commit hook or a core.hooksPath setting — but the gate could
not resolve it into a single invocation it can check.

Rewrite it in a shape the gate can read, or state the exception out loud:

  1. Drop the wrapper or the shell quoting and run `git commit …` directly.
  2. A guard is genuinely red and you must defer → ALLOW_UNWIRED=1 git commit ...

Why this is a deny and not a pass: the alternative is that every spelling the
gate has not enumerated becomes a silent bypass. Measured 2026-09-06 — a plain
`timeout 60 git commit -m x --no-verify` produced a commit with the guards never
running and this gate saying nothing at all.
"""

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
        out.append((m.group(2) or "", rest[:end.start()] if end else rest,
                    m.group(1) or ""))
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
    return [seg for _, seg, _env in commit_invocations(stripped)]


GIT_C_RE = re.compile(r"-C\s+(" + VALUE + r")")
GIT_CONFIG_RE = re.compile(r"-c\s+(" + VALUE + r")")
# 指令列前綴形式的環境變數：`GIT_CONFIG_COUNT=1 … git commit`。
ENV_ASSIGN_RE = re.compile(r"(?:^|\s)([A-Za-z_][A-Za-z0-9_]*)=(" + VALUE + r")")
# `git --config-env=<key>=<envvar>`：git 官方的第三條 transient config 通道，
# 語義等同 `-c`，只是值從環境變數取。
CONFIG_ENV_RE = re.compile(r"--config-env[= ](" + VALUE + r")")
# `GIT_CONFIG_PARAMETERS="'k'='v' 'k2'='v2'"`：第四條，較內部但目前仍有效。
CONFIG_PARAM_RE = re.compile(r"'([^']*)'\s*=\s*'([^']*)'")
# 任何提到 hooksPath 的寫法。這是**兜底**：解析不出來就擋，而不是放行。
HOOKSPATH_MENTION_RE = re.compile(r"hooks?path", re.I)
# 「這一段是在設定一個 git 設定值嗎」——`-c k=v`、`--config-env=k=v`、
# `GIT_CONFIG_KEY_n=k`、`GIT_CONFIG_PARAMETERS='k'='v'`。兜底只看這些片段，
# 不看整條指令列，否則 `grep -rn hooksPath .` 這種正常指令會被誤擋。
# `-c k=v` 這一條與上面的 `GIT_CONFIG_RE` 是**同一個東西**，別再開第二份：
# 兩份逐字相同、名字不同、相距十幾行，哪天有人收緊其中一邊，另一邊會靜默
# 保留舊行為，而**沒有任何測試分得出來**（2026-09-06 簡潔性鏡頭指出）。
CONFIG_ASSIGN_RE = GIT_CONFIG_RE
# 這幾種寫在 git **之前**，所以要掃整條指令列。
ENV_CONFIG_ASSIGN_RE = re.compile(
    r"(?:--config-env[= ]|GIT_CONFIG_KEY_\d+=|GIT_CONFIG_PARAMETERS=)"
    r"(" + VALUE + r"(?:\s*=\s*" + VALUE + r")?)")
# 設定的**鍵**裡出現 hooks 就算可疑：`core.hooks''Path`、`core.hooks$K` 這種
# 拼接／間接寫法，字面上沒有 `hooksPath`，但 git 收到的就是它。
HOOKS_IN_KEY_RE = re.compile(r"\bcore\.hooks", re.I)
# 續行的寫法**依 shell 而異**，不能兩種都認：bash 的行尾反引號是命令替換
# （`` TAG=`git describe` ``），把它當續行會把下一行併上來、讓 `git` 前面失去
# 分隔符，反而製造一個放行漏洞。工具名已經告訴我們是哪個 shell，就照它分。
CONTINUATION_RE = {
    "Bash": re.compile(r"\\\r?\n"),
    "PowerShell": re.compile(r"`\r?\n"),
}


def inline_config(options, line=""):
    """`-c k=v` from *this* invocation, as arguments for our own git call.

    `git -c core.hooksPath=/dev/null commit` points git at a hooks directory
    that has no pre-commit — a one-shot bypass that leaves no configuration
    behind. Asking git where hooks live *without* passing the same `-c` gives
    the answer for a different configuration than the one about to run.
    """
    args = []
    for pair in GIT_CONFIG_RE.findall(options):
        args += ["-c", pair.strip("\"'")]
    # `GIT_CONFIG_COUNT/KEY_n/VALUE_n` 是 git ≥2.31 的公開 API，與 `-c` 同義。
    # 只掃指令列的 `-c` 時，`GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath
    # GIT_CONFIG_VALUE_0=/nonexistent git commit` 會整個繞過這道閘：實測守衛
    # 一次都沒跑而 commit 成功，且 gate 沒有輸出任何 deny。
    # 兩種來源都要看：**指令列前綴**（`VAR=x git commit`，hook 子行程看不到，
    # 只能從指令字串撈）與**繼承的環境**。前綴站在 `git` 之前，而 `options`
    # 只涵蓋 `git` 與 `commit` 之間那一段，所以掃的是整條指令列。
    # ⚠ 第一版只掃 `options`，繞道照樣過——而我當時「驗證它被擋了」是假的：
    # 那個測試 repo 本來就會因為別的理由被擋。用正確接線的 repo 才測得到。
    whole = line or options
    inline_env = {k: v.strip("\"'") for k, v in ENV_ASSIGN_RE.findall(whole)}
    for src in (inline_env, os.environ):
        try:
            count = int(src.get("GIT_CONFIG_COUNT", "0"))
        except (TypeError, ValueError) as _q:
            note_quiet("inline_config", _q)
            count = 0
        for i in range(min(count, 64)):   # 上限：別讓一個大數字把我們卡住
            key = src.get("GIT_CONFIG_KEY_%d" % i)
            val = src.get("GIT_CONFIG_VALUE_%d" % i)
            if key and val is not None:
                args += ["-c", "%s=%s" % (key.strip("\"'"), val.strip("\"'"))]
        # 第四條通道：`GIT_CONFIG_PARAMETERS="'k'='v' 'k2'='v2'"`。
        # 指令列前綴形式的值自己就含引號與空白，一般的 `VAR=值` 切法會在第一個
        # 閉引號斷掉（實測只取到 `'core.hooksPath'`）。所以看到這個變數名時，
        # 直接在整條指令列上撈 `'k'='v'` 這個形狀。
        blob = src.get("GIT_CONFIG_PARAMETERS")
        if blob is None and "GIT_CONFIG_PARAMETERS" in whole:
            blob = whole
        for k, v in CONFIG_PARAM_RE.findall(blob or ""):
            args += ["-c", "%s=%s" % (k, v)]
    # 第三條通道：`git --config-env=<key>=<envvar>`，值從環境變數取。
    for pair in CONFIG_ENV_RE.findall(whole):
        pair = pair.strip("\"'")
        if "=" not in pair:
            continue
        key, envvar = pair.split("=", 1)
        val = inline_env.get(envvar, os.environ.get(envvar))
        if val is not None:
            args += ["-c", "%s=%s" % (key, val)]
    return args


def git_env_prefix(env_prefix, options=""):
    """指令列上那些**會改變 git 行為**的環境變數前綴。

    交給探測子行程，讓 git 自己解析實際生效的設定。只取 git 自己會讀的那些，
    不是整條指令列的所有賦值——後者會把使用者的任意變數帶進我們的子行程。
    """
    # 只傳「**指向一個設定檔**」的那幾個——它們的內容 gate 看不到，只能讓 git
    # 自己去讀。`GIT_CONFIG_PARAMETERS`／`GIT_CONFIG_COUNT` **刻意不傳**：
    # 它們已經由 `inline_config` 轉成 `-c`，而這裡的一般切法會把
    # `GIT_CONFIG_PARAMETERS='k'='v'` 在第一個閉引號截斷，餵給 git 一個壞值
    # ——git 報錯、探測失敗、fail-open 放行，等於用一個修法打開另一個洞。
    keep = ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_NOSYSTEM",
            "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR",
            "HOME", "USERPROFILE", "XDG_CONFIG_HOME")
    # `git --git-dir=<路徑>` 與 `--work-tree=` 是**指令列**上的同義寫法，
    # 效果與同名環境變數一樣。只掃 env 賦值時它們一個都收不到：實測
    # `git --git-dir=<剝掉 hooks 的 .git> --work-tree=<repo> commit -am x`
    # 真的產出 commit、哨兵不跑、gate 放行，而同語意的 `GIT_DIR=` 被擋下。
    # 這一段的檔頭註解早就知道這兩個選項會插在 `git` 與 `commit` 之間
    # （用來對樣式），卻沒把它們當成 hooks 改道——同一類沒掃完。
    out = {}
    for opt, var in (("git-dir", "GIT_DIR"), ("work-tree", "GIT_WORK_TREE"),
                     ("git-common-dir", "GIT_COMMON_DIR")):
        # `--git-dir` 這類在**選項段**（git 與 commit 之間），env 賦值在**前綴**，
        # 兩者是這一次呼叫的不同部位，都要各自傳進來——傳整條指令列的話，
        # 後面無關的段落會覆蓋或誤擋（那正是這一輪抓到的第三個同類實例）。
        m = re.search(r"--%s(?:=|\s+)(%s)" % (opt, VALUE), options)
        if m:
            out[var] = m.group(1).strip("\"'")
    for name, value in ENV_ASSIGN_RE.findall(env_prefix):
        if name in keep:
            out[name] = value.strip("\"'")
    return out


def unaccounted_hookspath(line, options, config_args):
    """指令裡提到 hooksPath，而我們沒能把它算進自己的探測——這種一律擋。

    這是**兜底**，也是這道閘這一輪學到的東西：git 至少有四條 transient config
    通道（`-c`、`GIT_CONFIG_COUNT/KEY/VALUE`、`--config-env`、
    `GIT_CONFIG_PARAMETERS`），而前三輪抗辯只想到前兩條——第三條是外部審查
    實測給出來的：`git --config-env=core.hooksPath=EMPTY commit` 讓守衛一次
    都沒跑而 **commit rc=0 成功**，gate 卻回 allow。

    列舉寫法永遠慢一步。真正的不變量是「git 實際會用的 hooksPath」，而這道閘
    看不到那個值（它是 PreToolUse，繼承不到指令列的 env 前綴）。看不到就不能
    假裝沒事：只要指令裡出現 `hooksPath` 而我們沒把它解析進探測參數，就擋。
    誤擋的代價是使用者多打一句說明；漏擋的代價是整道閘靜默失效。
    """
    # 只看**設定賦值**那些片段，不看整條指令列。看整條的話，
    # `grep -rn hooksPath .` 或一個叫 `test_hookspath.py` 的檔名就會擋掉 commit
    # ——誤擋比漏擋更糟，這道閘自己的檔頭就這樣寫（2026-09-06 抗辯實測）。
    #
    # 比對前先把引號拿掉：`git -c core.hooks''Path=<空目錄>` 是 shell 拼接，
    # 字面上沒有那個字，但 git 收到的是 `core.hooksPath`。同理 `core.hooks$K`
    # 這種變數間接——所以判準放寬成「設定的鍵裡出現 hooks」。
    # `-c` 只在 **git 自己的選項段**裡才算設定賦值。掃整條指令列的話，
    # `python -c "…core.hooksPath…"` 這種完全無關的 `-c` 會被當成 git 設定
    # ——寫這段的當下它就擋掉了我自己的一條驗證指令。
    settings = (CONFIG_ASSIGN_RE.findall(options)
                + ENV_CONFIG_ASSIGN_RE.findall(line))
    if not settings:
        return False
    suspicious = [s for s in settings
                  if HOOKS_IN_KEY_RE.search(s.replace("'", "").replace('"', ""))]
    if not suspicious:
        return False
    accounted = any(HOOKSPATH_MENTION_RE.search(a) for a in config_args)
    return not accounted


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


_QUOTED_SPAN_RE = re.compile(r"\$?'[^']*'|\"[^\"]*\"")
# 引號遮蔽之後，一個**裸的** `git … commit`。用來回答「這條指令列到底是不是在
# 做 commit」，而不必先能把它解析成一次可檢查的呼叫。
_BARE_GIT_COMMIT_RE = re.compile(
    r"(?:^|[;&|(){\n\r])[^;&|\n\r]*?\bgit(?:\.exe)?\s[^;&|\n\r]*?\bcommit\b")


def mask_quoted(text):
    """把引號內容換成等長的底線——`$'…'`（bash ANSI-C quoting）也算。

    `echo "git commit is fun"` 與 `timeout 60 git commit -n` 的差別，是前者的
    `git commit` **在引號裡**。不遮蔽就分不出來，而分不出來的代價是誤擋一整類
    文件與搜尋指令。
    """
    return _QUOTED_SPAN_RE.sub(lambda m: "_" * len(m.group(0)), text)


def unparsed_commit_risk(line):
    """解析不出呼叫、卻明顯是一次會繞過 hook 的 commit —— 回傳擋人理由。

    這道閘的檔頭寫著「偵測不到就擋」，而 `unaccounted_hookspath` 這個 fail-closed
    兜底掛在 `main` 的 SKIP 早退**下游**——也就是說「認不出來就擋」原本只適用於
    「已經被認出來的那些」。實測兩條繞道（2026-09-06 抗辯）：

      timeout 60 git commit -m x --no-verify        → 樣式比不中 → SKIP → 放行
      git -c core.hooksPath=$'/tmp/a b' commit -m x → 同上（`$'…'` 不在 VALUE 裡）

    範圍刻意收窄成這道閘真正在保護的兩件事（跳過 hook 的旗標、hooksPath），
    不是「所有解析不出來的 commit 都擋」——後者會讓 `git log --grep commit`
    這種唯讀指令變成誤擋，而誤擋比漏擋更糟。
    """
    masked = mask_quoted(line)
    if not _BARE_GIT_COMMIT_RE.search(masked):
        return ""
    if skips_the_hook(masked) or HOOKSPATH_MENTION_RE.search(masked):
        return UNPARSED_REASON
    return ""


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
    # `--amend` 以前整條回 SKIP，於是 `main` 在接線檢查之前就 return——
    # 一個 opt-in 卻沒接線的 repo，`git commit -m x` 被擋，
    # `git commit --amend -m x` 卻放行。實測 `git commit --amend --no-edit`
    # 與 `--amend -m` **兩種寫法都會執行 pre-commit**（git 2.53.0，哨兵印出
    # SENTINEL_RAN），所以那次 amend 同樣是「守衛一次都沒跑」的 commit
    # ——正是 W2 要抓的病，只是換一個旗標就免罰（2026-09-06 抗辯）。
    # 豁免它沒有留下任何理由，1.2.0 以來就是這樣。
    return "COMMIT"


def repo_root(cwd=None):
    """Absolute path of the enclosing git work tree, or None."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=5, cwd=cwd,
        )
    except Exception as _q:
        note_quiet("repo_root", _q)
        return None
    root = out.stdout.strip()
    return root if out.returncode == 0 and root else None


def precommit_path(root, config_args=(), env_prefix=None):
    """Where git will actually look for the pre-commit hook, or None.

    Not ``<root>/.git/hooks/pre-commit``: in a worktree or a submodule ``.git``
    is a *file*, so that path never exists and every commit was denied with a
    remedy (``cp … .git/hooks/pre-commit``) that cannot work there. The reverse
    error is just as real — with ``core.hooksPath`` set (husky, lefthook) that
    path can exist while git reads a different one, which would pass a repo
    whose guards never run. ``git rev-parse --git-path`` answers both.

    ⚠ **指令列上的環境變數前綴要交給這個子行程**（`env_prefix`），否則探測問的是
    「gate 自己的設定」而不是「這次 commit 會用的設定」。少了它，
    `GIT_CONFIG_GLOBAL=<檔> git commit`、`GIT_CONFIG_SYSTEM=…`、`HOME=<偽 home>`
    這些**指到一個設定檔**的寫法完全繞得過去：`hooksPath` 三個字從頭到尾不會
    出現在指令列上，字串比對永遠碰不到，而實測守衛沒跑、commit rc=0 成功。

    這才是 2026-09-06 外部審查那句話的正解——不要列舉語法，讓 git 自己去解析
    實際生效的設定。前一版加了 `--config-env` 與 `GIT_CONFIG_PARAMETERS` 兩條
    解析，那仍然是列舉，於是第五、第六條（GLOBAL／SYSTEM）當天就被找出來。
    """
    env = dict(os.environ)
    env.update(env_prefix or {})
    try:
        out = subprocess.run(
            ["git", *config_args, "rev-parse", "--git-path", "hooks/pre-commit"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=5,
            cwd=root, env=env,
        )
    except Exception as _q:
        note_quiet("precommit_path", _q)
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
# 提示檔在 repo 私有的 git 目錄裡，路徑由 `note_path()` 向 git 要。
# v1.4.x 曾放在 `~/.claude/state/` 並用 `FABLE_STATE_DIR` 讓測試改道；
# 兩者都已移除，因為那個位置需要從 repo 路徑推導檔名，而不同 repo 會撞名。
NOTE_REL = "fable/wiring_unregistered.txt"


def note_path(root):
    """提示檔的位置——**向 git 要**，不從 repo 路徑推導檔名。

    1.4.1 之前兩端各自把 repo 路徑的非英數字元換成底線來當檔名，那個對應
    不是一對一的：`x/evil-a`、`x/evil_a`、`x/evil/a` 撞成同一個檔名。1.4.1
    補了讀取端的 `repo:` 比對、1.5.0 補了寫入端的刪除比對，但兩者都只是
    「撞了之後不要造成傷害」——覆寫面補不起來：兩個都沒 opt-in 的碰撞 repo，
    後寫的一定蓋掉先寫的，而讓 A 因為「這是 B 的檔案」不寫，A 就永遠沒有提示。
    兩種選擇都有一方失去提示，因為根因是**拿路徑推導檔名**這件事本身。

    `--git-path` 讓 git 自己回答「這個 repo 的私有檔案放哪」：
      主 repo        → `.git/fable/…`（相對於 cwd）
      linked worktree → `…/.git/worktrees/<name>/fable/…`（絕對路徑，各自獨立）
    於是碰撞在結構上不可能發生，而不是被一道檢查擋住；同時兩端都問同一個
    來源，1.4.1 那種「Python 逐字元 vs `tr` 逐位元組」的雙端分歧也一併消失。

    `.git` 不會被 clone 帶走，所以一個惡意 repo 放不進東西——這正是提示檔
    不能搬進工作目錄的那個約束。
    """
    try:
        out = subprocess.run(["git", "rev-parse", "--git-path", NOTE_REL],
                             capture_output=True, encoding="utf-8",
                             errors="replace", timeout=5, cwd=root)
    except (OSError, subprocess.SubprocessError):  # quiet-ok: 提示檔路徑問不到，只影響提示，不影響判定
        return None
    if out.returncode != 0:
        return None
    p = (out.stdout or "").strip()
    if not p:
        return None
    # 主 repo 回的是相對 cwd 的路徑，worktree 回絕對路徑——兩種都要能用
    return p if os.path.isabs(p) else os.path.join(root, p)


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
    note = note_path(root)
    if note is None:
        return  # 問不到 git 就不留提示，絕不猜路徑
    if declared:
        # 宣告檔補上了就把提示收掉，否則它會永遠掛在每次 session 開場。
        # 路徑由 git 給，一個 repo 一份，刪的一定是自己的那一份。
        try:
            os.remove(note)
        except OSError:  # quiet-ok: 提示寫入失敗絕不影響 commit，且它不參與任何判定
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
        os.makedirs(os.path.dirname(note), exist_ok=True)
        with open(note, "w", encoding="utf-8", newline="") as fh:
            fh.write("repo: %s\n" % root)
            fh.write("\n".join(found) + "\n")
    except (OSError, subprocess.SubprocessError):  # quiet-ok: 同上，提示路徑的失敗不影響 commit 判定
        return  # 提示失敗絕不影響 commit


def check_wiring(root, config_args=(), env_prefix=None):
    """Return a deny reason, or None when the repo's guards are properly wired."""
    decl = os.path.join(root, DECL_REL)
    if not os.path.isfile(decl):
        return None  # repo has not opted in — do nothing at all

    installed = precommit_path(root, config_args, env_prefix)
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
    except OSError as _q:
        note_quiet("check_wiring unreadable hook", _q)
        return None  # unreadable → fail open, never break the session

    # 註解不算執行。`# TODO: run .claude/wiring-guards later` 這樣一行就足以讓
    # 這道檢查通過，而守衛一次都不會跑——實測把 runner 換成
    # `#!/bin/sh` + 一行註解 + `exit 0`，gate 回 ALLOW、commit 成立、守衛的
    # 計數檔一行都沒增加（2026-09-06 抗辯）。最可能的實際形態不是攻擊，是
    # 有人把 runner 那一段註解掉、卻留下說明它的那一行。
    executable_body = re.sub(r"#[^\n]*", "", body)
    if "wiring-guards" not in executable_body:
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
    except Exception as _q:
        note_quiet("main", _q)
        return 0  # fail-open: a gate must never break the session

    try:
        if payload.get("tool_name") not in ("Bash", "PowerShell"):
            return 0
        line = normalised(payload)
        if not commit_invocations(line):
            # 解析不出任何一次呼叫。fail-closed 兜底在這裡，**不是**在下面——
            # 掛在下游等於「認不出來就擋」只適用於認得出來的那些。
            risk = unparsed_commit_risk(line)
            if risk:
                root = repo_root()
                if root and os.path.isfile(os.path.join(root, DECL_REL)):
                    deny(risk)
            return 0
        # **每一個 commit 各自判定**，不是只判第一個。
        #
        # 這裡原本取 `invocations[0]` 決定 repo 與 opt-in，而 `classify` 是掃
        # **全部** segment 找 `--no-verify`。兩邊的範圍不一樣，於是只要第一個
        # commit 指向一個沒有 opt-in 的 repo，`not declared` 的早退就把後面那個
        # 真正的 `--no-verify` 連同判定一起丟掉。實測（2026-09-06 抗辯，
        # 已 opt-in 且正確接線的 repo，內含未 opt-in 的 vendor）：
        #   `git commit -am x --no-verify`                        → DENY
        #   `git -C vendor commit -m bump && git commit -am x --no-verify` → ALLOW
        #   `git -C vendor status && git commit -am x --no-verify` → DENY（對照組：
        #      `status` 不產生 commit invocation，所以 [0] 還是真的那個）
        # 107 條測試全綠，因為每一條 `--no-verify` 案都斷言在 `classify` 上，
        # 而 `classify` 是對的——沒有一條把整支 gate 端到端餵一條**多個 commit**
        # 的指令列。
        #
        # ⚠ 這是這個檔案自己記載過兩次的那一類的**第四個實例**：判定的範圍與
        # 取值的範圍不一致。前三次都是「該用單一呼叫的值，卻讀了整條指令列」，
        # 這一次方向相反——判定看了整條，取值只看第一個。
        seen_roots = set()
        for options, segment, own_env in commit_invocations(line):
            # **這一次呼叫自己的** env 前綴，不是整條指令列的。讀整條的話，
            # `git commit -m x ; GIT_CONFIG_GLOBAL=<乾淨的> true` 這種尾巴會覆蓋掉
            # 真正的前綴（漏擋），而 `git commit -m x && GIT_DIR=<別處> git log`
            # 這種無關的後段會讓 commit 被誤擋、還叫人去改另一個 repo 的 hooks。
            root = repo_root(cwd=target_dir(options))
            if not root:
                continue
            declared = os.path.isfile(os.path.join(root, DECL_REL))
            if root not in seen_roots:
                seen_roots.add(root)
                note_unregistered(root, declared)
            # W1 only applies to repos that opted in, so an unrelated repo using
            # --no-verify is none of this gate's business.
            if not declared:
                continue
            if skips_the_hook(segment):
                deny(W1_REASON)
                return 0
            config_args = inline_config(options, line)
            if unaccounted_hookspath(line, options, config_args):
                deny(HOOKSPATH_REASON)
                return 0
            reason = check_wiring(root, config_args, git_env_prefix(own_env, options))
            if reason:
                deny(reason)
                return 0
    except Exception as _q:
        note_quiet("main", _q)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
