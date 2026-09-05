# -*- coding: utf-8 -*-
"""wiring_gate（組件 4）與 wiring_runner 的驗收——接線閘門本身會不會被繞過。

驗收項目清單：
  W1 opt-in 邊界：repo 沒有 `.claude/wiring-guards` → 一律不介入（含 --no-verify）
  W2 `--no-verify` 在已宣告的 repo 被擋（那是繞過 pre-commit 的唯一無痕入口）
  W3 宣告了守衛卻沒有 `.git/hooks/pre-commit` → 擋（守衛全在、一個都不會跑）
  W4 pre-commit 存在但內容不提及宣告檔 → 擋（裝了別的 hook，守衛仍不會跑）
  W5 正確接線 → 放行
  W6 指令判定不受 commit 訊息內文左右（訊息裡寫到旗標不得讓整道閘放行）
  W7 `--amend`、非 commit 指令、其他工具 → SKIP；PowerShell 與 Bash 同樣受管
  W8 旗標只讀 `git commit` 那一段，且短旗標叢集要拆開：
     `-nm`／`-anm`／`--amend --no-verify` 要擋；`&& git log -n 1`、`; sort -n f` 不得擋
  W9 pre-commit 路徑向 git 問（`rev-parse --git-path`），不是拼 `.git/hooks/`
     ——worktree 的 `.git` 是檔案，拼出來的路徑永不存在
  W10 `git -c core.hooksPath=<空目錄> commit` 的一次性繞道 → 問 git 時要帶上同一個 -c
  W11 `git -C <path> commit` 提交的是 <path>，宣告檔要看那邊的
  W12 續行字元依 shell 而異：PowerShell 的 `` ` `` 是續行，bash 的行尾反引號是命令替換
  W13 未 opt-in 但已有接線型守衛的 repo → 留下提示檔（不擋 commit）
  W14 W13 的配對：補上宣告檔後提示必須被收掉，否則每次開場都嘮叨
  W15 一般 repo（沒有接線型守衛）→ 不留提示
  W16 提示必須真的被講出來——驅動真實 inject_protocol.sh 斷言它輸出提示內容
  R6 宣告檔存在卻一條守衛都沒有（空檔／只有註解）→ 紅，不得回綠
  R7 新增的紅燈也要走 ALLOW_UNWIRED 逃生口，否則 repo 會被完全鎖死
  R1 runner：會讀 stdin 的守衛不得吃掉宣告檔後續行（eval 必須 </dev/null）
  R2 runner：末行沒有換行字元時，最後一條仍要執行
  R3 runner：pytest 類指令零通過視為假綠，判紅
  R4 runner：ALLOW_UNWIRED=1 紅燈仍放行

執行命令：
  cd <repo> && python -m pytest tests/test_wiring_gate.py -v

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-09-05 11:35 GMT+8）
══════════════════════════════════════
對應：CHANGELOG 1.1.0「新增組件 4 接線閘門」。
本組件的來源是 2026-09-05 一個真實 repo 一天內挖出的四個「做了沒接線」實例：
限流器 WIRING_TODO 兩個月零呼叫、移除腳本因缺 BOM 從第一天跑不起來、
租約守門只擋住兩條重啟路徑之一、rebuild primitive 零呼叫端。四者都通過了驗收。

執行命令：python -m pytest tests/test_wiring_gate.py -v
最後執行：2026-09-05 14:59（三輪抗辯修復後）→ 57 passed ✅

併入本 repo 後的抽樣突變（在**這個** repo 實跑，不是引用來源 repo 的紀錄）：
  把 classify 裡的 strip_message_bodies(command) 改回 command
    → 3 failed, 24 passed（W6 三案翻紅）；還原 → 27 passed
  把 runner 的 eval "$cmd" </dev/null 改成 eval "$cmd"
    → 1 failed, 26 passed（R1 翻紅）；還原 → 27 passed

──────────────────────────────────────
2026-09-05 13:09 GMT+8：抗辯抓出的四個缺陷修復（W8／W9／R6）
──────────────────────────────────────
三鏡頭抗辯（skeptic／red-team／simplifier）對這支 gate 的判定全是 REFUTED，
以下四項為我逐條實跑重現後修掉的，每項各有一個突變證明對應測試會翻紅：
  M-A 只認獨立 `-n`（叢集漏擋）      → W8 `-anm` 案翻紅
  M-B 旗標掃整條指令列（誤擋）        → W8 `&& echo -n done` 案翻紅
  M-C `--amend` 先判（amend+no-verify 漏擋）→ W8 amend 案翻紅
  M-D 寫死 .git/hooks/pre-commit      → W9 翻紅
  M-E 拿掉零守衛偵測                  → R6 翻紅
每次突變只翻自己那一條，其餘保持綠；還原後 36 passed。
──────────────────────────────────────
2026-09-05 15:5x GMT+8：自動偵測未 opt-in 的 repo（W13～W16，v1.3.0）
──────────────────────────────────────
來由：`~/.claude/CLAUDE.md:347-348` 早已定案「hook 在沒有宣告檔時會掃 repo 內的
接線型守衛，有守衛卻沒宣告就出一句提示（不擋 commit）」，但實作它的
`pre_commit_wiring_gate.sh` 在今天的收斂（commit 494d3cc）被刪除，而 Fable 版
從來沒有這段——決議還在、行為沒了。本批補回。

提示走「寫檔＋SessionStart 注入」而不是 hook 自己說話，理由有兩份獨立證據：
被刪那支的檔頭記著外審實測「CC 在 exit 0 時直接丟棄 stderr，提示從未出現過」，
官方文件亦載明 PreToolUse 的 allow 不顯示理由、且無 additionalContext 欄位。

三個突變（各只翻自己那條，還原後 200 passed）：
  M-a 拿掉掃描（回到純 opt-in）→ W13、W14 翻紅
  M-b 補上宣告後不清提示        → W14 翻紅
  M-c SessionStart 不注入提示    → W16 翻紅
最後執行：2026-09-05 15:5x → 61 passed ✅

最後執行：2026-09-05 14:59 → 57 passed ✅（13:09 曾連跑 5 次皆綠，
未複現 skeptic 回報的 R1 偶發紅燈，該現象標 UNVERIFIED，見下方 ⏳）

fail-then-pass：W6 是本檔存在的主因——修復前 gate 拿【整條指令字串】比對，
於是訊息裡寫到 `--amend` 就被判成 amend 而整道閘靜默放行；把 classify 裡的
`strip_message_bodies(command)` 改回 `command` 可重現該紅燈。
R1/R2/R3 同理：拿掉 `</dev/null`、拿掉 `|| [ -n "$line" ]`、拿掉假綠偵測，
各自讓對應案例翻紅，且**未修時三者的 rc 都是 0**——會一邊跳過守衛一邊報綠。

✅ 已驗收（本檔涵蓋）
  W1-W7 判定與擋放行為；R1-R4 runner 行為（皆驅動真實檔案，非測試裡複製的邏輯）
⏳ 待驗收（本檔未涵蓋）
  R1 的偶發紅燈：2026-09-05 抗辯過程中，某次全量跑出現一次
    `test_r1...` 斷言 `0 == 1`（runner 回 0、無 RED 行），其後連跑 12 次未複現。
    現況標 `UNVERIFIED`——症狀與「宣告檔讀取失敗→靜默回綠」同形，本輪已補
    `[ -r "$DECL" ]` 檢查（見 R6 那批），但**尚未證明兩者是同一件事**。
    解鎖條件＝在 CI 或高負載環境重複跑到複現，或證明該路徑已不可能回綠。
  Claude Code 真的把 deny JSON 當成拒絕：本檔只驗到 gate 吐出正確的 deny 封包，
  沒有驗到 harness 收到它之後真的擋下那次 Bash 呼叫。解鎖條件＝在真實 session 裡
  對一個已 opt-in 的 repo 下 `git commit --no-verify` 並觀察它被拒（INSTALL.md 步驟 10）。
"""
import json
import re
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(ROOT, ".claude", "hooks", "wiring_gate.py")
RUNNER = os.path.join(ROOT, ".claude", "hooks", "wiring_runner.sh")

sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
import wiring_gate  # noqa: E402

HEREDOC_MSG = (
    "git commit -F - <<'MSGEOF'\n"
    "fix: x\n"
    "\n"
    "never use --no-verify\n"
    "MSGEOF"
)


def _bash(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def _git_repo(tmp_path, declare=True, precommit=None):
    """Build a throwaway git repo; optionally opt it in and install a hook."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    if declare:
        d = tmp_path / ".claude"
        d.mkdir()
        (d / "wiring-guards").write_text("true\n", encoding="utf-8")
    if precommit is not None:
        hooks = tmp_path / ".git" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        (hooks / "pre-commit").write_text(precommit, encoding="utf-8")
    return tmp_path


def _run_gate(payload, cwd):
    out = subprocess.run(
        [sys.executable, GATE], input=json.dumps(payload),
        capture_output=True, text=True, cwd=str(cwd), timeout=30,
    )
    assert out.returncode == 0, f"gate 不得非零退出（fail-open 契約）: {out.stderr}"
    return out.stdout.strip()


def _is_deny(stdout):
    if not stdout:
        return False
    return json.loads(stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── 判定層（不碰檔案系統）────────────────────────────────────────────
@pytest.mark.parametrize("cmd,expect", [
    ('git commit -m "fix: x"', "COMMIT"),
    ('git commit --amend -m "x"', "SKIP"),
    ('git commit --no-verify -m "x"', "NOVERIFY"),
    ('git commit -n -m "x"', "NOVERIFY"),
    ('git add -A && git commit -m "x"', "COMMIT"),
    ('ALLOW_UNWIRED=1 git commit -m "x"', "COMMIT"),
    ('git -C /repo commit -m "x"', "COMMIT"),
    ("git log --oneline -5", "SKIP"),
    ('echo "git commit is fun"', "SKIP"),
    ("pytest -q", "SKIP"),
])
def test_w7_classification(cmd, expect):
    assert wiring_gate.classify(_bash(cmd)) == expect


@pytest.mark.parametrize("cmd", [
    'git commit -m "gate: forbid --amend as a bypass"',
    "git commit -m 'why --no-verify is banned'",
    'git commit --message="about --amend"',
    HEREDOC_MSG,
])
def test_w6_message_body_does_not_steer_the_verdict(cmd):
    """訊息內文含旗標字樣時，仍必須是一般 commit。

    修復前拿整條字串比對，這四種寫法全部讓整道閘靜默放行——
    而寫這套機制的那次 commit，訊息裡正好同時有 --amend 與 --no-verify。
    """
    assert wiring_gate.classify(_bash(cmd)) == "COMMIT"


@pytest.mark.parametrize("cmd,expect", [
    # 短旗標叢集：`-nm` 就是 `-n -m`。只認獨立的 `-n` 時整道閘放行。
    ('git commit -nm "x"', "NOVERIFY"),
    ('git commit -anm "x"', "NOVERIFY"),
    # amend 與 no-verify 併用：先判 amend 會整個 SKIP，等於第二條無痕繞道。
    ('git commit --amend --no-verify -m "x"', "NOVERIFY"),
    # 後面那個命令的旗標不歸這道閘管——這是誤擋，比漏擋更糟。
    ('git commit -m "x" && git log -n 1', "COMMIT"),
    ('git commit -am "x"; sort -n f', "COMMIT"),
    ('git commit -m "x" && echo -n done', "COMMIT"),
    # 叢集旗標帶訊息內文：剝訊息時不得把 -n 一起剝掉，也不得被內文影響判定。
    ('git commit -am "never use --no-verify"', "COMMIT"),
    # 一列裡有兩個 commit，第二個才帶 -n：只看第一段就會放行。
    ('git commit -m "x" && git commit -n -m "y"', "NOVERIFY"),
    # 兩個都是 amend 才算 SKIP；一個 amend 一個不是，仍要走接線檢查。
    ('git commit --amend --no-edit && git commit -m "y"', "COMMIT"),
    ('git commit --amend --no-edit; git commit --amend -m "y"', "SKIP"),
    # 換行也是命令分隔符：多行 shell 是代理最常寫的形態，而它原本讓整道閘失效。
    ('git add -A\ngit commit --no-verify -m "x"', "NOVERIFY"),
    ('cd .\ngit commit -m "x"', "COMMIT"),
    # 續行（bash 的 \、PowerShell 的 `）之後的旗標仍屬同一個命令。
    ('git commit -m "x" \\\n  --no-verify', "NOVERIFY"),
    # 吃值的短旗標：值裡有 n 不代表 -n。誤擋比漏擋更糟。
    ('git commit -Sjohn -m "x"', "COMMIT"),
    ('git commit -CHEAD', "COMMIT"),
    # git 的全域選項不只 -c／-C，插在中間原本讓整個樣式比不中。
    ('git --no-pager commit -n -m "x"', "NOVERIFY"),
    ('git --git-dir=.git --work-tree=. commit -n -m "x"', "NOVERIFY"),
    ('git.exe commit -n -m "x"', "NOVERIFY"),
    # 引號：git 讀 "-n" 就是那個旗標，字串比對讀不出來。
    ('git commit "-n" -m "x"', "NOVERIFY"),
    # 長旗標的唯一前綴縮寫：git 吃 --no-veri，--no-verbose 則是另一個旗標。
    ('git commit --no-veri -m "x"', "NOVERIFY"),
    ('git commit --no-verbose -m "x"', "COMMIT"),
    # `--` 之後都是路徑，即使長得像旗標。
    ('git commit -m "x" -- -notes.txt', "COMMIT"),
    # bash 的行尾反引號是命令替換，不是續行——當成續行會併掉分隔符而放行。
    ('TAG=`git describe`\ngit commit -n -m "x"', "NOVERIFY"),
    # -C 屬於它自己那個 git 呼叫；掃全指令會被前面的 -C 帶到別的 repo。
    ('git -C /other status && git commit -n -m "x"', "NOVERIFY"),
])
def test_w8_flags_are_read_per_command_and_per_cluster(cmd, expect):
    """W8：旗標判定的三個已兌現缺陷（2026-09-05 實測，全部同一類：把整條指令當一個旗標池）。

    ① 叢集短旗標沒拆開 → `-nm` 漏擋　② `--amend` 先判 → amend+no-verify 漏擋
    ③ 掃整條指令列 → `git log -n 1`／`echo -n`／`sort -n` 誤擋。
    """
    assert wiring_gate.classify(_bash(cmd)) == expect


def test_w9_hook_path_comes_from_git_not_from_string_concat(tmp_path):
    """W9：worktree 裡 `.git` 是**檔案**，拼出來的 .git/hooks/pre-commit 永不存在。

    修復前：已 opt-in 的 repo 在 worktree 內每次 commit 恆被擋，
    而 deny 訊息教的 `cp ... .git/hooks/pre-commit` 在該情境也做不到——無法自救。
    """
    main = tmp_path / "main"
    repo = _git_repo(main, precommit="#!/bin/sh\n# runs .claude/wiring-guards\n")
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    wt = tmp_path / "wt"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", str(wt)], check=True)
    assert (wt / ".git").is_file(), "前提不成立：worktree 的 .git 應該是檔案"

    assert _run_gate(_bash('git commit -m "x"'), wt) == "", (
        "worktree 內接線正確卻被擋——gate 拼了一個永遠不存在的路徑"
    )


def test_w10_inline_hookspath_config_is_honoured(tmp_path):
    """W10：`git -c core.hooksPath=<空目錄> commit` 是一次性的 bypass。

    問 git「hook 在哪」時若不帶上同一個 `-c`，得到的是**另一種設定**下的答案：
    gate 看到已裝好的 .git/hooks/pre-commit 而放行，實際執行的 commit 卻去讀
    那個空目錄，守衛一條都不會跑。設定不會留在 repo 裡，因此也查不到痕跡。
    """
    repo = _git_repo(tmp_path, precommit="#!/bin/sh\n# runs .claude/wiring-guards\n")
    empty = tmp_path / "nohooks"
    empty.mkdir()
    cmd = 'git -c core.hooksPath=%s commit -m "x"' % empty.as_posix()
    out = _run_gate(_bash(cmd), repo)
    assert _is_deny(out), "一次性 -c core.hooksPath 繞過未被抓到"
    assert "no pre-commit hook" in out


def test_w11_git_c_targets_another_repo(tmp_path):
    """W11：`git -C <path> commit` 提交的是 <path>，不是目前所在的 repo。

    gate 原本問的是 session 的 cwd，於是從一個沒宣告的目錄對已宣告的 repo
    下 commit 就整個走過去了。
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    subprocess.run(["git", "init", "-q", str(outside)], check=True)
    target = _git_repo(tmp_path / "target", precommit=None)  # 已宣告、未裝 hook
    cmd = 'git -C %s commit -m "x"' % target.as_posix()
    out = _run_gate(_bash(cmd), outside)
    assert _is_deny(out), "跨 repo commit 沒有套用目標 repo 的宣告"


def test_r7_allow_unwired_also_escapes_the_zero_guard_red(tmp_path):
    """R7：新增的紅燈必須走同一個逃生口，否則 repo 會被鎖死。

    宣告檔只剩註解時，runner 判紅、而 `--no-verify` 又被 W1 擋——
    若 ALLOW_UNWIRED 對這條紅燈無效，該 repo 就完全無法 commit。
    沒有出口的閘門，下一步一定是被整個刪掉。
    """
    rc, out = _run_runner(tmp_path, "# 只有註解\n", env={"ALLOW_UNWIRED": "1"})
    assert rc == 0 and "accepted on the record" in out


def _note_path(state_dir, repo):
    safe = re.sub(r"[^A-Za-z0-9]", "_", str(repo))
    return state_dir / f"wiring_unregistered_{safe}.txt"


def _commit_with_state(repo, state_dir):
    out = subprocess.run(
        [sys.executable, GATE], input=json.dumps(_bash('git commit -m "x"')),
        capture_output=True, text=True, cwd=str(repo), timeout=30,
        env=dict(os.environ, FABLE_STATE_DIR=str(state_dir)))
    assert out.returncode == 0
    return out.stdout.strip()


def test_w13_repo_with_guards_but_no_declaration_leaves_a_note(tmp_path):
    """W13：opt-in 的反面失效——沒人記得 opt-in 的 repo 裡，這道閘什麼都不做。

    所以看到「這個 repo 已經在寫接線型守衛」時要留下一句提示。提示走檔案、
    由 SessionStart 注入，因為 PreToolUse 沒有「不擋人又能說話」的輸出：
    allow 會丟掉理由、exit 0 的 stderr 被丟棄。
    """
    repo = _git_repo(tmp_path / "r", declare=False)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_gate_entrypoints.py").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    state = tmp_path / "state"

    assert _commit_with_state(repo, state) == "", "未 opt-in 的 repo 不得被擋"
    note = _note_path(state, repo)
    assert note.exists(), "有守衛卻沒宣告，卻沒有留下任何提示"
    body = note.read_text(encoding="utf-8")
    # git 回的路徑用正斜線，Windows 的 Path 用反斜線——比對前先正規化
    assert "test_gate_entrypoints.py" in body
    assert str(repo).replace("\\", "/") in body.replace("\\", "/")


def test_w14_note_is_cleared_once_the_repo_opts_in(tmp_path):
    """W14：W13 的配對——宣告檔補上了就要把提示收掉。

    否則它會永遠掛在每次 session 開場，而每次都出現的提示會被當成雜訊略過。
    """
    repo = _git_repo(tmp_path / "r", precommit="#!/bin/sh\n# .claude/wiring-guards\n")
    state = tmp_path / "state"
    state.mkdir()
    note = _note_path(state, repo)
    note.write_text("repo: x\nstale\n", encoding="utf-8")

    _commit_with_state(repo, state)
    assert not note.exists(), "已經 opt-in 了，提示卻還留著"


def test_w15_ordinary_repo_gets_no_note(tmp_path):
    """W15：一般 repo 不留提示——會對每個專案說話的東西，很快就會被關掉。"""
    repo = _git_repo(tmp_path / "r", declare=False)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_math.py").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    state = tmp_path / "state"

    _commit_with_state(repo, state)
    assert not _note_path(state, repo).exists(), "對沒有接線型守衛的 repo 也出聲"


def test_w16_sessionstart_actually_surfaces_the_note(tmp_path):
    """W16：提示必須真的被講出來——寫了沒人讀，正是這道閘要抓的病。

    驅動真實的 inject_protocol.sh，斷言它把提示內容輸出出來（SessionStart 的
    輸出會進模型上下文，這是唯一已驗證可達的路徑）。
    """
    repo = _git_repo(tmp_path / "r", declare=False)
    home = tmp_path / "home"
    (home / ".claude" / "state").mkdir(parents=True)
    note = _note_path(home / ".claude" / "state", repo)
    note.write_text("repo: %s\ntests/test_gate_entrypoints.py\n" % repo, encoding="utf-8")

    inject = os.path.join(ROOT, ".claude", "hooks", "inject_protocol.sh")
    out = subprocess.run(["sh", inject], capture_output=True, encoding="utf-8",
                         errors="replace", cwd=str(repo), timeout=60,
                         env=dict(os.environ, HOME=str(home)))
    assert "FABLE-PROTOCOL" in out.stdout, "協議本體沒被注入"
    assert "尚未 opt-in" in out.stdout, "提示檔存在，SessionStart 卻沒講出來"
    assert "test_gate_entrypoints.py" in out.stdout


def test_w7_other_tools_are_ignored():
    assert wiring_gate.classify(
        {"tool_name": "Read", "tool_input": {"command": "git commit"}}) == "SKIP"


def test_w12_continuation_is_read_per_shell():
    """W12：續行字元依 shell 而異，兩種都認會反過來開一個洞。

    PowerShell 的行尾 `` ` `` 是續行；bash 的行尾反引號是**命令替換**，
    把它當續行會把下一行併上來、讓 `git` 前面失去分隔符而整條漏判。
    """
    ps_continued = 'git commit -m "x" `\n  --no-verify'
    assert wiring_gate.classify(
        {"tool_name": "PowerShell", "tool_input": {"command": ps_continued}}) == "NOVERIFY"
    # 同一個字串在 bash 是兩件事：一個 commit，加上一段命令替換的殘骸。
    assert wiring_gate.classify(_bash(ps_continued)) == "COMMIT"


def test_w7_powershell_is_covered_too():
    """PowerShell 工具必須與 Bash 同樣受管，否則換個工具就是零痕跡繞過。"""
    assert wiring_gate.classify(
        {"tool_name": "PowerShell",
         "tool_input": {"command": 'git commit -m "x"'}}) == "COMMIT"


# ── 接線層（真的建 repo）──────────────────────────────────────────────
def test_w1_repo_without_declaration_is_untouched(tmp_path):
    """未 opt-in 的 repo 零介入——連 --no-verify 都不管，那是別人的事。"""
    repo = _git_repo(tmp_path, declare=False)
    assert _run_gate(_bash('git commit --no-verify -m "x"'), repo) == ""
    assert _run_gate(_bash('git commit -m "x"'), repo) == ""


def test_w2_no_verify_denied_when_opted_in(tmp_path):
    repo = _git_repo(tmp_path, precommit="#!/bin/sh\n# runs .claude/wiring-guards\n")
    assert _is_deny(_run_gate(_bash('git commit --no-verify -m "x"'), repo))


def test_w3_declared_but_no_precommit_installed(tmp_path):
    """守衛全在、一個都不會跑——.git/hooks 不入版控，re-clone 後不會回來。"""
    repo = _git_repo(tmp_path, precommit=None)
    out = _run_gate(_bash('git commit -m "x"'), repo)
    assert _is_deny(out)
    assert "no pre-commit hook" in out


def test_w4_precommit_exists_but_never_runs_the_declaration(tmp_path):
    """裝了別的 pre-commit：hook 存在，守衛照樣不會執行。"""
    repo = _git_repo(tmp_path, precommit="#!/bin/sh\nnpm run lint\n")
    out = _run_gate(_bash('git commit -m "x"'), repo)
    assert _is_deny(out)
    assert "never runs the wiring guards" in out


def test_w5_properly_wired_passes(tmp_path):
    repo = _git_repo(tmp_path, precommit='#!/bin/sh\nDECL=".claude/wiring-guards"\n')
    assert _run_gate(_bash('git commit -m "x"'), repo) == ""


def test_gate_fails_open_on_garbage_input(tmp_path):
    """契約：gate 絕不可弄壞 session。"""
    out = subprocess.run([sys.executable, GATE], input="not json{",
                         capture_output=True, text=True,
                         cwd=str(tmp_path), timeout=30)
    assert out.returncode == 0 and out.stdout.strip() == ""


# ── runner 層（驅動真的 wiring_runner.sh）─────────────────────────────
def _run_runner(tmp_path, decl_text, env=None):
    decl = tmp_path / "decl"
    decl.write_text(decl_text, encoding="utf-8", newline="")
    e = dict(os.environ, WIRING_DECL=str(decl))
    e.update(env or {})
    out = subprocess.run(["sh", RUNNER], capture_output=True, text=True,
                         cwd=str(tmp_path), env=e, timeout=120)
    return out.returncode, out.stdout + out.stderr


def test_r1_guard_reading_stdin_must_not_eat_later_lines(tmp_path):
    """第一條讀 stdin。少了 </dev/null 它會吃光宣告檔，第二條永不執行且回綠。"""
    rc, out = _run_runner(tmp_path, "cat > /dev/null\nfalse # R1_SENTINEL\n")
    assert rc == 1 and "R1_SENTINEL" in out


def test_r2_final_line_without_newline_still_runs(tmp_path):
    rc, out = _run_runner(tmp_path, "true\nfalse # R2_SENTINEL")
    assert rc == 1 and "R2_SENTINEL" in out


def test_r3_pytest_with_zero_passing_is_false_green(tmp_path):
    rc, out = _run_runner(tmp_path, 'echo "no tests ran" # pytest\n')
    assert rc == 1 and "no test actually passed" in out


def test_r4_allow_unwired_lets_a_red_guard_through(tmp_path):
    rc, out = _run_runner(tmp_path, "false # R4\n", env={"ALLOW_UNWIRED": "1"})
    assert rc == 0 and "accepted on the record" in out


def test_r5_all_green_exits_zero(tmp_path):
    rc, _ = _run_runner(tmp_path, "# comment\ntrue\ntrue\n")
    assert rc == 0


def test_r6_declaration_with_no_guards_is_red(tmp_path):
    """R6：宣告檔存在卻一條守衛都沒有 → 紅。

    空的（或只有註解的）宣告檔會讓 runner 每次都回綠，外觀上是一道閘、
    實際上放行所有 commit。與 R3 同類：**沒有執行任何東西**不是通過。
    """
    rc, out = _run_runner(tmp_path, "# 只有註解\n\n")
    assert rc == 1 and "declares no guards" in out
