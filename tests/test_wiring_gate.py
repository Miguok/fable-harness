# -*- coding: utf-8 -*-
"""wiring_gate（組件 4）與 wiring_runner 的驗收——接線閘門本身會不會被繞過。

驗收項目清單：
  W1 opt-in 邊界：repo 沒有 `.claude/wiring-guards` → 一律不介入（含 --no-verify）
  W2 `--no-verify` 在已宣告的 repo 被擋（那是繞過 pre-commit 的唯一無痕入口）
  W3 宣告了守衛卻沒有 `.git/hooks/pre-commit` → 擋（守衛全在、一個都不會跑）
  W4 pre-commit 存在但內容不提及宣告檔 → 擋（裝了別的 hook，守衛仍不會跑）
  W5 正確接線 → 放行
  W6 指令判定不受 commit 訊息內文左右（訊息裡寫到旗標不得讓整道閘放行）
  W7 非 commit 指令、其他工具 → SKIP；PowerShell 與 Bash 同樣受管
     （`--amend` 2026-09-06 起改回 COMMIT：實測它會執行 pre-commit，見 W38）
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
  W22 W14 的配對：收提示只能收自己的——碰撞檔名上別的 repo 的提示不得被刪或覆寫
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

──────────────────────────────────────
2026-09-05 23:25 GMT+8：碰撞類別的寫入面（W22）——外審 P2-01
──────────────────────────────────────
來由：外部審查（ChatGPT GPT-5.6 Sol，`reports/open_design_questions_review_20260905_chatgpt_reply_2026-09-05.md`）
指出 v1.4.1 只修了碰撞類別的**讀取面**。實查屬實：`inject_protocol.sh:17` 有第一行
`repo:` 比對，而 `wiring_gate.py` 的 `declared` 分支直接 `os.remove(note)`——
A 補上宣告檔會刪掉碰撞 repo B 的提示，B 永遠不會知道（被刪與從未產生同形）。

執行命令：python -m pytest tests/test_wiring_gate.py -q -k "w14 or w22"
最後執行：2026-09-06 14:1x → 109 passed ✅（全套 360 passed in 37.77s）
第六輪抗辯新增 W37／W38，兩條都以突變驗過：
  main 退回只判第一個 commit → W37 紅。⚠ 這是一個**已兌現的 P0**：
    `git -C vendor commit -m bump && git commit -am x --no-verify` 在 opt-in
    且正確接線的 repo 上實測 **ALLOW**，而裸的同一條 DENY。`classify` 掃全部
    segment、`main` 只取 invocations[0]，範圍不一致。107 條測試全綠是因為每一條
    --no-verify 案都斷言在 classify 上，而 classify 是對的。
  amend 豁免復活 → W38 紅。amend 原本整條回 SKIP，於是沒接線的 repo 換一個旗標
    就免罰；實測 `git commit --amend --no-edit` 與 `--amend -m` 都會執行
    pre-commit（git 2.53.0，哨兵印出 SENTINEL_RAN）。

（以下為 09-06 13:40 那批的紀錄）
最後執行：2026-09-06 13:40 → 107 passed ✅（全套 352 passed in 33.62s）
本輪（第五、六輪抗辯）新增 W32-W36，逐條突變驗過：
  git_env_prefix 改回讀整條指令列 → W33 紅
  runner 的 WIRING_DECL 環境接縫復活 → W34 紅
  包裝器退回只認 command／time → W35 的 9 個參數紅（`env`／`sudo`／`nice`／
    `nohup` 包裝的 --no-verify 原本回 SKIP，也就是閘完全不介入）
  GIT_COMMON_DIR 從 keep 拿掉 → W36 紅。⚠ 補這條之前它零覆蓋，而實測
    `GIT_COMMON_DIR=<剝掉 hooks 的同一份 .git> git commit` **commit 成立、
    pre-commit 一次都沒跑**（git 2.53.0.windows.1）。

（以下為 09-05 23:25 那批的紀錄）
最後執行：2026-09-05 23:25 → 2 passed ✅（全套 216 passed）

fail-then-pass 實測值：
  修法前（`git stash push -- .claude/hooks/wiring_gate.py`）
    → 1 failed, 1 passed：W22 `AssertionError: opt-in 時刪掉了別的 repo 的提示`
  修法後 → 2 passed
  ⚠ 過程中 W14 也曾翻紅一次，那是**真實缺陷不是測試噪音**：note 的 `repo:` 行由
  生產端以 `git rev-parse --show-toplevel` 寫入（Windows 上正斜線），而 W14 原本
  用 `WindowsPath`（反斜線）造 fixture。fixture 已改成向 git 要路徑，不寫死任一形式。

W14 原本的 fixture 寫的是 `repo: x`（別人的提示）卻斷言它必須被刪——
那條測試把缺陷編碼成了預期行為，與 W22 直接對撞。已改為寫入自己的 repo 路徑，
於是 W14／W22 成為一組「必須仍然做得到／必須被擋下」的配對。

✅ 已驗收（本檔涵蓋）
  W1-W7 判定與擋放行為；R1-R4 runner 行為（皆驅動真實檔案，非測試裡複製的邏輯）
  W22 寫入端的刪除路徑：不屬於自己的提示檔不得被刪
⏳ 待驗收（本檔未涵蓋）
  碰撞檔名的**覆寫**面仍開著：兩個 repo 都未 opt-in 且檔名相撞時，後寫的一方
    會覆蓋先寫的一方，而 ownership check 修不了它——A 若因為「這是 B 的檔案」
    而不寫，A 就永遠得不到提示，兩種選擇都有一方失去提示。
    根因是「拿 repo 路徑推導檔名」這個設計本身，不是缺一道檢查。
    解鎖條件＝改用不會碰撞的命名（外審建議 `git rev-parse --git-path`），
    見 `reports/open_design_questions_disposition_20260905.md` 票 F-04／F-05。
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
import shutil
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
    # `--amend` 不再豁免：實測兩種 amend 寫法都會執行 pre-commit，所以
    # opt-in 卻沒接線的 repo 用 amend 一樣是「守衛沒跑」的 commit。
    ('git commit --amend -m "x"', "COMMIT"),
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
    # amend 與非 amend 混在一列，兩者都要走接線檢查。
    ('git commit --amend --no-edit && git commit -m "y"', "COMMIT"),
    ('git commit --amend --no-edit; git commit --amend -m "y"', "COMMIT"),
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


def _note_path(repo):
    """提示檔路徑——**問 git**，不從 repo 路徑推導檔名。

    1.4.x 的這個 helper 用 shell 端的算法重算一次檔名，因為當時真的有兩份
    算法（Python 逐字元 vs `tr` 逐位元組）可能分歧。1.5.0 把兩端都改成問
    `git rev-parse --git-path` 之後，那個分歧類別在結構上消失了——再留著
    重算，等於把一份已經死掉的算法養在測試裡，而它永遠不會再翻紅。

    這裡問的是 git，與生產端問的是**同一個權威來源**，不是互相抄。
    """
    p = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-path",
                        "fable/wiring_unregistered.txt"],
                       capture_output=True, encoding="utf-8",
                       check=True).stdout.strip()
    return repo / p if not os.path.isabs(p) else type(repo)(p)


def _commit(repo, utf8_mode=None, cmd='git commit -m "x"'):
    env = dict(os.environ)
    if utf8_mode is not None:
        env["PYTHONUTF8"] = utf8_mode
    out = subprocess.run(
        [sys.executable, GATE], input=json.dumps(_bash(cmd)),
        capture_output=True, encoding="utf-8", errors="replace",
        cwd=str(repo), timeout=30, env=env)
    assert out.returncode == 0, f"gate 不得非零退出：{out.stderr[:300]}"
    assert not out.stderr.strip(), f"gate 不得吐 stderr：{out.stderr[:300]}"
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

    assert _commit(repo) == "", "未 opt-in 的 repo 不得被擋"
    note = _note_path(repo)
    assert note.exists(), "有守衛卻沒宣告，卻沒有留下任何提示"
    body = note.read_text(encoding="utf-8")
    # git 回的路徑用正斜線，Windows 的 Path 用反斜線——比對前先正規化
    assert "test_gate_entrypoints.py" in body
    assert str(repo).replace("\\", "/") in body.replace("\\", "/")


def test_w14_note_is_cleared_once_the_repo_opts_in(tmp_path):
    """W14：W13 的配對——宣告檔補上了就要把提示收掉。

    否則它會永遠掛在每次 session 開場，而每次都出現的提示會被當成雜訊略過。

    提示檔**由閘自己寫出來**，不手造 fixture：手造的話，這條測到的是我對
    檔案格式的想像，而不是寫入端與刪除端是否對得上。2026-09-05 就吃過一次
    ——手造的 fixture 用反斜線路徑，生產端用 git 的正斜線，兩者對不上。
    """
    repo = _git_repo(tmp_path / "r", declare=False,
                     precommit="#!/bin/sh\n# .claude/wiring-guards\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_gate_entrypoints.py").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)

    _commit(repo)
    note = _note_path(repo)
    assert note.exists(), "前置不成立：閘沒先寫出提示，這條就測不到收提示"

    # 現在才 opt-in
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "wiring-guards").write_text("true\n", encoding="utf-8")
    _commit(repo)
    assert not note.exists(), "已經 opt-in 了，提示卻還留著"


def test_w22_note_lives_where_a_hostile_repo_cannot_put_one(tmp_path):
    """W22：提示檔必須在 git 私有目錄內，不在工作目錄裡。

    提示的內容會被 SessionStart 注入上下文。它一旦落在工作目錄，就變成一個
    **repo 可以 commit 的東西**——任何人 clone 一份惡意 repo，開場就吃下對方
    寫好的內容。這是提示檔搬家方案唯一不可協商的約束（1.5.0 的抗辯否決了
    搬進 `<repo>/.fable/` 的版本，就是為了這條）。

    `.git` 滿足它：不被 clone 帶走、不進 `git status`、`git ls-files` 看不到。
    這條測的是那三個性質本身，不是「路徑字串裡有沒有 .git」——後者換個寫法
    就繞過去了。
    """
    repo = _git_repo(tmp_path / "r", declare=False)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_gate_entrypoints.py").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)

    _commit(repo)
    note = _note_path(repo)
    assert note.exists(), "前置不成立：沒有提示檔就測不到它放在哪"

    tracked = subprocess.run(["git", "-C", str(repo), "ls-files"],
                             capture_output=True, encoding="utf-8",
                             check=True).stdout
    assert "wiring_unregistered" not in tracked, "提示檔進了版控——會隨 clone 散佈"

    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                            capture_output=True, encoding="utf-8",
                            check=True).stdout
    assert "wiring_unregistered" not in status, "提示檔出現在 git status，會被誤 add"

    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True)
    assert not _note_path(clone).exists(), "提示檔被 clone 帶走了"


def test_w18_colliding_repo_paths_no_longer_share_a_note(tmp_path):
    """W18：舊命名把路徑的非英數字元全換成底線，於是不同 repo 撞成同一個檔名。

    `x/evil-a`、`x/evil_a`、`x/evil/a` 三者同名。1.4.1 補了讀取端的 `repo:`
    比對、1.5.0 補了刪除端的比對，但那些都只是「撞了之後不要造成傷害」；
    **覆寫**面補不起來，因為兩個都沒 opt-in 的碰撞 repo，後寫的必然蓋掉先寫的。

    這條盯的是**根因**：檔名不再由路徑推導，所以撞不起來。斷言的是兩個在舊
    命名下同名的 repo 現在拿到不同的路徑——換言之，它抓得到「有人把命名改
    回從路徑推導」這件事，不論那個新算法長什麼樣。

    ⚠ 斷言對象必須是**生產端的 `wiring_gate.note_path`**，不是本檔的
    `_note_path` helper。第一版寫成後者，於是它量的是測試自己的 git 查詢——
    把生產端整個換回 1.4.x 的共用目錄＋路徑推導，這條照樣綠（2026-09-06 實測）。
    守衛的斷言對象與被保護對象必須是同一份東西，否則它只是在證明我想像中的
    形狀會被抓到。
    """
    a = _git_repo(tmp_path / "evil-a", declare=False)
    b = _git_repo(tmp_path / "evil_a", declare=False)

    def old(p):
        return re.sub(rb"[^A-Za-z0-9]", b"_",
                      str(p).encode("utf-8")).decode("ascii")

    assert old(a) == old(b), "前置不成立：這兩個路徑在舊命名下並不相撞"

    pa, pb = wiring_gate.note_path(str(a)), wiring_gate.note_path(str(b))
    assert pa and pb, "生產端算不出提示檔路徑"
    assert os.path.abspath(pa) != os.path.abspath(pb), (
        "兩個舊命名下同名的 repo 仍共用同一個提示檔——命名又回到從路徑推導了"
    )


def test_w15_ordinary_repo_gets_no_note(tmp_path):
    """W15：一般 repo 不留提示——會對每個專案說話的東西，很快就會被關掉。"""
    repo = _git_repo(tmp_path / "r", declare=False)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_math.py").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    state = tmp_path / "state"

    _commit(repo)
    assert not _note_path(repo).exists(), "對沒有接線型守衛的 repo 也出聲"


def test_w16_sessionstart_actually_surfaces_the_note(tmp_path):
    """W16：提示必須真的被講出來——寫了沒人讀，正是這道閘要抓的病。

    驅動真實的 inject_protocol.sh，斷言它把提示內容輸出出來（SessionStart 的
    輸出會進模型上下文，這是唯一已驗證可達的路徑）。

    提示檔由**閘自己寫**，不手造：一端寫、另一端讀，才抓得到兩端對不上的
    分歧——手造 fixture 只證明「我想像的格式讀得出來」。
    """
    repo = _git_repo(tmp_path / "r", declare=False)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_gate_entrypoints.py").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    _commit(repo)
    assert _note_path(repo).exists(), "前置不成立：閘沒寫出提示檔"

    inject = os.path.join(ROOT, ".claude", "hooks", "inject_protocol.sh")
    out = subprocess.run(["sh", inject], capture_output=True, encoding="utf-8",
                         errors="replace", cwd=str(repo), timeout=60)
    assert "FABLE-PROTOCOL" in out.stdout, "協議本體沒被注入"
    assert "尚未 opt-in" in out.stdout, "提示檔存在，SessionStart 卻沒講出來"
    assert "test_gate_entrypoints.py" in out.stdout


def test_w17_note_survives_a_non_ascii_repo_path(tmp_path):
    """W17：路徑含非 ASCII 時，寫入端與讀取端必須算出**同一個**檔名。

    Python 的 `re.sub` 逐字元、shell 的 `tr` 逐位元組——中文目錄下
    `d_____repo` vs `d_________repo`，提示寫得出來卻永遠讀不到。
    本條**同時驅動兩端**（gate 寫、inject_protocol.sh 讀），這是唯一能抓到
    分歧的做法；只驗其中一端等於拿自己的算法跟自己比。
    """
    repo = _git_repo(tmp_path / "測試專案", declare=False)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_gate_entrypoints.py").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    home = tmp_path / "home"
    (home / ".claude" / "state").mkdir(parents=True)

    # PYTHONUTF8=0：那是原廠 zh-TW／ja／ko Windows 的預設。作者機器設了 =1，
    # 於是這條測試曾經「只在作者機器上綠」——它證明的是作者的環境，不是修法。
    _commit(repo, utf8_mode="0")

    inject = os.path.join(ROOT, ".claude", "hooks", "inject_protocol.sh")
    out = subprocess.run(["sh", inject], capture_output=True, encoding="utf-8",
                         errors="replace", cwd=str(repo), timeout=60,
                         env=dict(os.environ, HOME=str(home)))
    assert "test_gate_entrypoints.py" in out.stdout, (
        "非 ASCII 路徑下提示讀不到——寫入端與讀取端的檔名算法分歧"
    )


def test_w21_cjk_file_names_stay_readable_in_the_note(tmp_path):
    """W21：檔名本身含中文時，提示要是可讀的檔名，不是八進位跳脫。

    `git ls-files` 不加 `-z` 會把非 ASCII 檔名轉成 `"tests/test_\\346\\270\\254…"`。
    正則照樣命中、提示照樣寫出來——但對目標讀者是一串亂碼。
    W17 抓不到這條：它的**目錄**是中文，**檔名**是 ASCII。
    """
    repo = _git_repo(tmp_path / "r", declare=False)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_測試_wiring.py").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    state = tmp_path / "state"

    _commit(repo)
    body = _note_path(repo).read_text(encoding="utf-8")
    assert "test_測試_wiring.py" in body, f"檔名沒保持可讀：{body!r}"


def test_w20_gate_still_blocks_in_a_cjk_path_under_platform_default(tmp_path):
    """W20：中文路徑 ＋ `PYTHONUTF8=0`（原廠 zh-TW Windows）下，`--no-verify` 仍要被擋。

    這是本 kit 最嚴重的一次失效：`subprocess.run(..., text=True)` 以 locale
    （cp950）去解 git 的 UTF-8 輸出 → UnicodeDecodeError → `.strip()` 拿到
    None → AttributeError → 被 main 的 fail-open 吞掉 → **整道閘對 CJK 路徑全滅**，
    而且會吐一段 traceback 到 stderr。

    1.4.1 只改了「檔名怎麼算」，沒改**更早的那層：輸出怎麼解碼**——同一類的
    第二個實例。這條測試盯的是解碼那一層，所以它抓得到還沒發生的第三個。
    """
    repo = _git_repo(tmp_path / "測試專案",
                     precommit="#!/bin/sh\n# runs .claude/wiring-guards\n")
    state = tmp_path / "state"
    out = _commit(repo, utf8_mode="0",
                             cmd='git commit --no-verify -m "x"')
    assert _is_deny(out), "CJK 路徑下 --no-verify 沒被擋——整道閘對這些使用者是關的"


def test_w19_note_output_is_bounded(tmp_path):
    """W19：提示內容是從 repo 讀來的**檔名**——一個惡意 repo 能塞任意文字。

    寫入端有 8 筆上限，讀取端原本沒有：5000 行的提示檔會整包進上下文。
    行數與單行長度都要有上限。
    """
    repo = _git_repo(tmp_path / "m", declare=False)
    # 驅動**寫入端**：截斷發生在那裡（以字元為單位），手寫提示檔會繞過它，
    # 而能手寫 ~/.claude/state 的人本來就能做更糟的事——不在威脅模型內。
    # 檔名長度受 Windows 路徑上限拘束，取 129 字元（>120 的截斷點即可）。
    for i in range(12):
        (repo / ("test_" + "x" * 112 + f"{i}_wiring.py")).write_text(
            "x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    home = tmp_path / "home"
    state = home / ".claude" / "state"
    state.mkdir(parents=True)
    _commit(repo)

    inject = os.path.join(ROOT, ".claude", "hooks", "inject_protocol.sh")
    out = subprocess.run(["sh", inject], capture_output=True, encoding="utf-8",
                         errors="replace", cwd=str(repo), timeout=60,
                         env=dict(os.environ, HOME=str(home)))
    # 直接斷言兩個上限本身，不用「總長度小於某個大數字」——那種門檻是拍腦袋的，
    # 拿掉單行截斷仍然會綠（實測 6597 < 20000）。
    # 兩端各自都要有上限：讀取端的 `sed -n '2,9p'` 會蓋住寫入端沒截的情形，
    # 所以直接盯提示檔本身，否則寫入端的 [:8] 是沒有守衛的。
    note_lines = _note_path(repo).read_text(encoding="utf-8").splitlines()
    assert len(note_lines) <= 9, f"提示檔筆數沒有上限：{len(note_lines) - 1}"
    entries = [ln for ln in out.stdout.splitlines() if ln.startswith("  - ")]
    assert len(entries) <= 8, f"注入的筆數沒有上限：{len(entries)}"
    longest = max((len(ln) for ln in entries), default=0)
    assert longest <= 130, f"單行沒有長度上限：最長 {longest}"


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
    e = dict(os.environ)
    e.update(env or {})
    # 宣告檔的位置用**參數**傳，不用環境變數：環境變數版是生產環境的靜默繞道
    # （`WIRING_DECL=<無害檔案> git commit` 讓守衛一次都不跑而 rc=0），
    # 而 git 呼叫 pre-commit 時不帶參數，所以參數版在生產環境沒有這個縫。
    out = subprocess.run(["sh", RUNNER, str(decl)], capture_output=True, text=True,
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


@pytest.mark.parametrize("cmd,label", [
    ("GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath "
     "GIT_CONFIG_VALUE_0=/nonexistent git commit -m x", "指令列前綴形式"),
    ('GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=user.name GIT_CONFIG_VALUE_0=x '
     'GIT_CONFIG_KEY_1=core.hooksPath GIT_CONFIG_VALUE_1=/nonexistent '
     'git commit -m x', "夾在多筆設定裡"),
])
def test_w23_git_config_env_is_not_a_way_around_the_gate(tmp_path, cmd, label):
    """W23：`GIT_CONFIG_*` 環境變數與 `-c` 同義，兩者都不得繞過這道閘。

    `GIT_CONFIG_COUNT/KEY_n/VALUE_n` 是 git ≥2.31 的公開 API。W10 早就擋了
    `git -c core.hooksPath=…` 這條一次性繞道，但只掃指令列的 `-c`——於是同一件事
    換個寫法就整個過去了。2026-09-06 抗辯實測：守衛一次都沒跑、commit 成功，
    而 gate 沒有輸出任何 deny。

    這條盯的是**類別**（「這次呼叫用了什麼設定」有兩種來源），不是被回報的
    那一個變數名。W10 是它的配對：兩種寫法都要擋，缺一邊就等於沒擋。
    """
    # repo **正確接線**：不加旗標時是放行的。這樣唯一的變因就是這條繞道。
    # 第一版用「pre-commit 不提宣告檔」的 repo，於是它因為**別的理由**就被擋，
    # 把修法整個拿掉照樣綠——測試擋對了，但擋的不是它宣稱在擋的那件事。
    repo = _git_repo(tmp_path, precommit="#!/bin/sh\n# runs .claude/wiring-guards\n")
    assert not _is_deny(_run_gate(_bash("git commit -m x"), repo)), \
        "前置不成立：這個 repo 本來就被擋，測不出繞道有沒有生效"
    out = _run_gate(_bash(cmd), repo)
    assert _is_deny(out), f"{label}：這條繞道沒被擋，接線閘等於關著"


def test_w23b_a_harmless_git_config_env_is_not_blocked(tmp_path):
    """W23b：W23 的配對——與 hooks 無關的 `GIT_CONFIG_*` 不得誤擋。

    沒有這條，一個「看到 GIT_CONFIG_ 就擋」的實作也會讓 W23 全綠，而那會
    讓每個設定 user.name 的人都被擋下來。
    """
    repo = _git_repo(tmp_path, precommit="#!/bin/sh\n# runs .claude/wiring-guards\n")
    out = _run_gate(_bash(
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=user.name GIT_CONFIG_VALUE_0=x "
        "git commit -m x"), repo)
    assert not _is_deny(out), "正確接線的 repo 被無關的設定誤擋了"


def _wired_repo_with_sentinel(tmp_path):
    """一個正確接線的 repo，pre-commit 是會出聲並回非零的哨兵。

    用真實 git 跑，因為這一組要證明的是「git 到底有沒有執行那個 hook」——
    只測 gate 的解析器會回到它出事的那個模式：測我想到的寫法，不是測不變量。
    """
    repo = _git_repo(tmp_path, precommit=(
        "#!/bin/sh\n# runs .claude/wiring-guards\necho SENTINEL_RAN\nexit 99\n"))
    os.chmod(str(repo / ".git" / "hooks" / "pre-commit"), 0o755)
    (repo / "f.txt").write_text("x\n", encoding="utf-8", newline="")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    return repo


def _commit_with(repo, extra_args=(), env=None):
    e = dict(os.environ)
    e.update(env or {})
    r = subprocess.run(
        ["git"] + list(extra_args) + ["-c", "user.email=t@t", "-c", "user.name=t",
                                      "commit", "-m", "probe"],
        cwd=str(repo), capture_output=True, encoding="utf-8",
        errors="replace", env=e, timeout=60)
    return "SENTINEL_RAN" in (r.stdout + r.stderr)


def test_w24_the_sentinel_really_runs_on_an_ordinary_commit(tmp_path):
    """W24：前置——正常 commit 時 git **真的**執行了那個 hook。

    沒有這條，下面兩條「哨兵沒跑」就證明不了任何事：一個根本不會跑 hook 的
    fixture 會讓它們全綠。
    """
    assert _commit_with(_wired_repo_with_sentinel(tmp_path)), \
        "前置不成立：正常 commit 也沒跑 pre-commit，這組測試量不到東西"


@pytest.mark.parametrize("args,env,label", [
    (["--config-env=core.hooksPath=FABLE_HOOKS"], {"FABLE_HOOKS": "@EMPTY@"},
     "--config-env（git 官方第三條 transient config 通道）"),
    ([], {"GIT_CONFIG_PARAMETERS": "'core.hooksPath'='@EMPTY@'"},
     "GIT_CONFIG_PARAMETERS（第四條）"),
])
def test_w25_hookspath_overrides_really_skip_the_hook_and_must_be_denied(
        tmp_path, args, env, label):
    """W25：這兩條真的會讓 hook 完全不執行，所以必須被擋。

    2026-09-06 外部審查（ChatGPT GPT-5.6 Sol）指出並實測，而**三輪內部抗辯
    全都沒看到**。`--config-env=core.hooksPath=EMPTY` 的實測結果是哨兵沒跑、
    **commit rc=0 直接成功**，而 gate 回 allow——完整的假綠。

    這條先驗「繞道真的成立」（哨兵沒跑）再驗「gate 擋下來」。少了前半，
    測試會退化成「gate 對某個字串回 deny」，而那不是被保護的東西。
    """
    empty = tmp_path / "no-hooks"
    empty.mkdir()
    repo = _wired_repo_with_sentinel(tmp_path / "r")
    real_env = {k: v.replace("@EMPTY@", str(empty).replace("\\", "/"))
                for k, v in env.items()}
    real_args = [a.replace("@EMPTY@", str(empty).replace("\\", "/")) for a in args]

    assert not _commit_with(repo, real_args, real_env), (
        f"{label}：前置不成立，這條繞道沒有真的跳過 hook，測試量不到東西"
    )

    prefix = " ".join(f"{k}={v}" for k, v in real_env.items())
    cmd = ("%s git %s commit -m probe" % (prefix, " ".join(real_args))).strip()
    assert _is_deny(_run_gate(_bash(cmd), repo)), f"{label}：繞道沒被擋"


def test_w25b_an_unrelated_config_env_is_not_blocked(tmp_path):
    """W25b：W25 的配對——與 hooksPath 無關的 `--config-env` 不得誤擋。

    沒有這條，「看到 --config-env 就擋」也會讓 W25 全綠，而那會擋掉一個
    git 官方支援的正常用法。
    """
    repo = _git_repo(tmp_path, precommit="#!/bin/sh\n# runs .claude/wiring-guards\n")
    out = _run_gate(_bash(
        "MYNAME=alice git --config-env=user.name=MYNAME commit -m x"), repo)
    assert not _is_deny(out), "無關的 --config-env 被誤擋了"


@pytest.mark.parametrize("how,label", [
    ("local", "git config --local core.hooksPath"),
    ("global", "GIT_CONFIG_GLOBAL 指到自製設定檔"),
    ("inherited", "環境變數由外面繼承進來"),
])
def test_w26_hookspath_set_where_the_command_line_cannot_show_it(tmp_path, how, label):
    """W26：從指令列看不到的地方設 hooksPath，一樣要擋。

    W23／W25 擋的是寫在指令列上的三種通道，靠字串解析。但 hooksPath 也可以
    寫在 `.git/config`、`GIT_CONFIG_GLOBAL` 指到的檔案、或先前已經 export 的
    環境變數裡——那些**指令列上一個字都看不到**，字串解析永遠碰不到。

    這些之所以擋得住，是因為這道閘**問 git** 拿 pre-commit 的位置
    （`rev-parse --git-path`），而 git 自己會把那些設定算進去。也就是說它問的
    是**實際狀態**而不是「我列得出來的語法」——那正是這一批修法真正的價值，
    而在這條測試之前，它一行守衛都沒有。

    每一條都先驗「繞道真的成立」（哨兵沒跑）再驗「gate 擋下來」；少了前半，
    測試會退化成「gate 對某個情境回 deny」，而那不是被保護的東西。
    """
    empty = tmp_path / "no-hooks"
    empty.mkdir()
    e = str(empty).replace("\\", "/")
    repo = _wired_repo_with_sentinel(tmp_path / "r")

    env = {}
    if how == "local":
        subprocess.run(["git", "-C", str(repo), "config", "--local",
                        "core.hooksPath", e], check=True)
    elif how == "global":
        cfg = tmp_path / "fake-global"
        cfg.write_text("[core]\n\thooksPath = %s\n" % e,
                       encoding="utf-8", newline="")
        env["GIT_CONFIG_GLOBAL"] = str(cfg)
    else:
        env["GIT_CONFIG_PARAMETERS"] = "'core.hooksPath'='%s'" % e

    assert not _commit_with(repo, (), env), (
        f"{label}：前置不成立，這條沒有真的跳過 hook，測試量不到東西"
    )

    out = subprocess.run(
        [sys.executable, GATE], input=json.dumps(_bash("git commit -m x")),
        capture_output=True, text=True, cwd=str(repo), timeout=30,
        env=dict(os.environ, **env))
    assert out.returncode == 0, f"gate 不得非零退出：{out.stderr[:300]}"
    assert _is_deny(out.stdout.strip()), f"{label}：沒被擋"


def test_w26b_the_control_repo_is_allowed(tmp_path):
    """W26b：W26 的配對——沒有任何 override 時，正確接線的 repo 必須放行。

    這條看起來多餘，實際上不是：W26 三條的第一版全部「通過」，而那是因為
    測試 repo 的 pre-commit 沒提到宣告檔、**因為別的理由**被擋。沒有這條對照，
    一個永遠 deny 的實作會讓 W26 全綠（2026-09-06 實際踩到，這是第二次）。
    """
    repo = _wired_repo_with_sentinel(tmp_path / "r")
    assert _commit_with(repo), "前置不成立：對照組的 hook 根本沒跑"
    assert not _is_deny(_run_gate(_bash("git commit -m x"), repo)), \
        "沒有任何 override，正確接線的 repo 卻被擋"


_HP = "hooks" + "Path"   # 拆開寫：這個檔案本身不該觸發那道閘


@pytest.mark.parametrize("var", ["GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"])
def test_w27_a_config_file_pointed_at_by_a_prefix_variable_is_followed(tmp_path, var):
    """W27：用**指令列前綴**指到一個設定檔，一樣要擋。

    2026-09-06 第四輪抗辯與外部審查同時指出的第五、第六條通道。它們與前四條
    有本質差別：`%s` 三個字**從頭到尾不會出現在指令列上**，它在那個檔案裡。
    所以字串比對的兜底永遠碰不到，實測守衛沒跑而 commit rc=0 成功。

    修法不是再列一種語法，是把指令列上的環境變數前綴**交給探測子行程**，
    讓 git 自己去解析實際生效的設定。這才是「不要拿列得出來的語法當契約」
    那句話的正解——第五、第六條之所以存在，正因為前一版又是一次列舉。

    W26 測的是**繼承**形式（gate 的環境裡就有），那一格本來就擋得住；
    這一條測的是**前綴**形式，hook 行程繼承不到——兩者是不同的格子。
    """ % _HP
    empty = tmp_path / "no-hooks"
    empty.mkdir()
    cfg = tmp_path / "evil.cfg"
    cfg.write_text("[core]\n\t%s = %s\n" % (_HP, str(empty).replace("\\", "/")),
                   encoding="utf-8", newline="")
    repo = _wired_repo_with_sentinel(tmp_path / "r")

    assert not _commit_with(repo, (), {var: str(cfg)}), (
        f"{var}：前置不成立，這條沒有真的跳過 hook"
    )
    cmd = "%s=%s git commit -m x" % (var, cfg)
    assert _is_deny(_run_gate(_bash(cmd), repo)), f"{var}：前綴形式沒被擋"


@pytest.mark.parametrize("spelling", [
    "core.hooks''Path",
    'core.hooks""Path',
    "core.hoo'ks'Path",   # 拆在 hooks **中間**：前綴比對救不了，只有正規化能擋
])
def test_w28_quote_splitting_does_not_hide_the_key(tmp_path, spelling):
    """W28：用引號把設定鍵拆開，字面上沒有那個字，但 git 收到的就是它。"""
    empty = tmp_path / "no-hooks"
    empty.mkdir()
    repo = _wired_repo_with_sentinel(tmp_path / "r")
    cmd = "git -c %s=%s commit -m x" % (spelling, str(empty).replace("\\", "/"))
    assert _is_deny(_run_gate(_bash(cmd), repo)), f"{spelling}：拼接寫法沒被擋"


@pytest.mark.parametrize("cmd", [
    "grep -rn %s . ; git add -A && git commit -m x",
    "git add tests/test_%s.py && git commit -m x",
    'git commit -m "note: core.%s is how husky works"',
    'python -c "print(1)" && git commit -m x',
])
def test_w29_mentioning_the_word_elsewhere_is_not_a_bypass(tmp_path, cmd):
    """W29：W27／W28 的配對——只是**提到**那個字不得被誤擋。

    兜底一度掃整條指令列，於是 `grep -rn …` 、一個叫 `test_…​.py` 的檔名、
    甚至 `python -c "…"` 裡的 `-c` 都會擋掉 commit。這道閘自己的檔頭寫著
    「誤擋比漏擋更糟，會讓人把整道閘關掉」——而寫兜底的當下它就擋掉了我
    自己的一條驗證指令（2026-09-06）。

    現在兜底只看**git 自己的設定賦值片段**：`-c` 只在 git 的選項段裡算，
    其餘只認 `--config-env=`／`GIT_CONFIG_KEY_n=`／`GIT_CONFIG_PARAMETERS=`。
    """
    repo = _git_repo(tmp_path, precommit="#!/bin/sh\n# runs .claude/wiring-guards\n")
    line = cmd % _HP if "%s" in cmd else cmd
    assert not _is_deny(_run_gate(_bash(line), repo)), f"誤擋：{line}"


def test_w30_git_dir_redirect_is_denied_and_work_tree_is_not(tmp_path):
    """W30：把 env 交給探測之後，兩個方向都要對。

    `GIT_DIR=<別的 repo>/.git` 讓 git 用別人的 hooks——實測哨兵不跑，必須擋。
    `GIT_WORK_TREE=<別處>` **不會**改 hooks 的位置——實測哨兵照跑，不得誤擋。

    ⚠ 我原本以為兩個都該擋，是實測推翻了那個推論。這一對寫在一起，是因為
    「把使用者控制的環境變數餵進自己的 git 子行程」是 2026-09-06 新開的面，
    而它同時可能造成漏擋與誤擋——只驗一邊會漏掉另一邊。
    """
    repo = _wired_repo_with_sentinel(tmp_path / "r")
    other = _git_repo(tmp_path / "other", declare=True)   # 沒有 pre-commit

    assert not _commit_with(repo, (), {"GIT_DIR": str(other / ".git")}), \
        "前置不成立：GIT_DIR 沒有真的讓 hook 不跑"
    assert _commit_with(repo, (), {"GIT_WORK_TREE": str(other)}), \
        "前置不成立：GIT_WORK_TREE 竟然讓 hook 不跑了（與實測相反）"

    deny = _run_gate(_bash("GIT_DIR=%s git commit -m x" % (other / ".git")), repo)
    assert _is_deny(deny), "GIT_DIR 指到別的 repo，守衛不會跑，卻沒被擋"

    allow = _run_gate(_bash("GIT_WORK_TREE=%s git commit -m x" % other), repo)
    assert not _is_deny(allow), "GIT_WORK_TREE 不影響 hooks，卻被誤擋"


def test_w31_a_hostile_home_gitconfig_does_not_get_executed(tmp_path):
    """W31：把 `HOME` 交給探測，不得變成執行任意指令的入口。

    這道閘為了不再列舉 hooksPath 的寫法，改成把指令列上的環境變數前綴餵進
    自己的 git 子行程。那是**使用者控制的值進入我們的行程**——如果 git 會因為
    某個設定去執行東西（`core.pager`、`core.sshCommand`、`core.fsmonitor`、
    alias），一道防繞道的修法就變成了任意指令執行。

    實測 `git rev-parse` 不碰這些（哨兵檔案沒被建立），所以這條是**回歸守衛**：
    哪天探測換成別的 git 子指令，它會叫。
    """
    marker = tmp_path / "PWNED.txt"
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text(
        "[core]\n\tpager = touch %s\n\tsshCommand = touch %s\n"
        "\tfsmonitor = touch %s\n[alias]\n\trev-parse = !touch %s\n"
        % (marker, marker, marker, marker), encoding="utf-8", newline="")
    repo = _wired_repo_with_sentinel(tmp_path / "r")

    _run_gate(_bash("HOME=%s git commit -m x" % home), repo)
    assert not marker.exists(), (
        "探測讀了惡意 .gitconfig 並執行了它的指令——防繞道的修法變成了 RCE"
    )


@pytest.mark.parametrize("form", ["=", " "])
def test_w32_git_dir_on_the_command_line_is_followed_too(tmp_path, form):
    """W32：`git --git-dir <別的 .git>` 與環境變數同義，兩種拼法都要擋。

    W30 擋的是 `GIT_DIR=` 環境變數。指令列上的 `--git-dir` 是同一件事，而
    2026-09-06 的實測是：`=` 的寫法漏擋、**空格的寫法連 commit 都沒被認出來**
    ——`GIT_GLOBAL_OPT` 只認 `--opt=value`，於是 `git --git-dir /alt/.git commit`
    整條樣式比不中，整道閘完全不介入。兩個層次的洞疊在同一個選項上。

    這條先驗「繞道真的成立」（哨兵不跑）再驗 gate 擋下來。
    """
    alt = tmp_path / "alt.git"
    repo = _wired_repo_with_sentinel(tmp_path / "r")
    import shutil
    shutil.copytree(str(repo / ".git"), str(alt))
    shutil.rmtree(str(alt / "hooks"), ignore_errors=True)

    args = (["--git-dir=%s" % alt, "--work-tree=%s" % repo] if form == "="
            else ["--git-dir", str(alt), "--work-tree", str(repo)])
    assert not _commit_with(repo, args), "前置不成立：這條沒有真的跳過 hook"

    sep = "=" if form == "=" else " "
    cmd = "git --git-dir%s%s --work-tree%s%s commit -m x" % (sep, alt, sep, repo)
    assert _is_deny(_run_gate(_bash(cmd), repo)), f"--git-dir（{form!r} 寫法）沒被擋"


def test_w33_a_decoy_later_on_the_line_does_not_override_this_invocation(tmp_path):
    """W33：指令列後段的同名變數不得覆蓋掉這一次呼叫自己的前綴。

    `git_env_prefix` 一度讀**整條指令列**，於是
    `GIT_CONFIG_GLOBAL=<惡意> git commit -m x ; GIT_CONFIG_GLOBAL=<乾淨> true`
    會讓探測讀到後面那個乾淨的值而放行——守衛不跑、commit 成立。

    這是同一類的**第三個**實例：`commit_invocations` 與 `target_dir` 的說明
    都寫著「從整條指令列讀會讓整道閘關掉」，而它已經被修過兩次。類別是
    「讀這一次呼叫自己的範圍，不是讀整行」。
    """
    empty = tmp_path / "no-hooks"
    empty.mkdir()
    evil = tmp_path / "evil.cfg"
    evil.write_text("[core]\n\t%s = %s\n" % (_HP, str(empty).replace("\\", "/")),
                    encoding="utf-8", newline="")
    clean = tmp_path / "clean.cfg"
    clean.write_text("[user]\n\tname = x\n", encoding="utf-8", newline="")
    repo = _wired_repo_with_sentinel(tmp_path / "r")

    cmd = ("GIT_CONFIG_GLOBAL=%s git commit -m x ; GIT_CONFIG_GLOBAL=%s true"
           % (evil, clean))
    assert _is_deny(_run_gate(_bash(cmd), repo)), "後段的誘餌把真正的前綴蓋掉了"


def test_w33b_an_unrelated_later_segment_is_not_a_false_deny(tmp_path):
    """W33b：W33 的配對——commit 之後**無關**的段落不得讓 commit 被誤擋。

    同一個缺陷的另一個方向：讀整行時，`git commit -m x && GIT_DIR=<別處> git log`
    會讓 commit 被擋，而且擋人的說明還叫你去改**另一個 repo** 的 hooks——
    照做會改到不相干的專案，而且修不好眼前這個。
    """
    other = _git_repo(tmp_path / "other", declare=False)
    repo = _wired_repo_with_sentinel(tmp_path / "r")
    cmd = "git commit -m x && GIT_DIR=%s git log --oneline -1" % (other / ".git")
    assert not _is_deny(_run_gate(_bash(cmd), repo)), "無關的後段造成誤擋"


def test_w34_the_runner_has_no_environment_seam(tmp_path):
    """W34：runner 不得有「用環境變數換掉宣告檔」的接縫。

    `DECL="${WIRING_DECL:-…}"` 是為了測試而開的，但它是**生產環境的靜默繞道**：
    實測 `WIRING_DECL=<內容只有 true 的檔案> git commit` → 守衛一次都沒跑、
    rc=0、commit 成立、**沒有任何訊息**。比官方認可的 `ALLOW_UNWIRED=1` 還糟，
    後者至少印一行留痕。而它在任何文件、甚至 runner 自己的檔頭都沒被提過。

    「為了測試而在生產程式碼上開的縫」正是這套工具存在的理由，而它就在自己
    身上。改用參數之後生產環境沒有這個縫：git 呼叫 pre-commit 時不帶參數。
    """
    decl = tmp_path / "real"
    decl.write_text('sh -c "echo REAL-GUARD-RAN >&2; exit 1"\n',
                    encoding="utf-8", newline="")
    harmless = tmp_path / "harmless"
    harmless.write_text("true\n", encoding="utf-8", newline="")

    work = tmp_path / "w"
    work.mkdir()
    (work / ".claude").mkdir()
    (work / ".claude" / "wiring-guards").write_text(
        'sh -c "echo REAL-GUARD-RAN >&2; exit 1"\n', encoding="utf-8", newline="")

    out = subprocess.run(["sh", RUNNER], capture_output=True, text=True,
                         cwd=str(work), timeout=120,
                         env=dict(os.environ, WIRING_DECL=str(harmless)))
    both = out.stdout + out.stderr
    assert "REAL-GUARD-RAN" in both, (
        "WIRING_DECL 換掉了宣告檔——測試接縫變成生產環境的靜默繞道"
    )
    assert out.returncode != 0, "守衛紅了卻回綠"


@pytest.mark.parametrize("cmd,expect", [
    # 讓 `git commit --no-verify` 原封不動跑起來的包裝器。原本只認
    # `command`／`time`，其餘三種整條樣式比不中——回的不是誤判成 COMMIT，
    # 是 SKIP：閘完全不介入（2026-09-06 抗辯實測三條全 SKIP）。
    ("env git commit --no-verify -m x", "NOVERIFY"),
    ("sudo git commit --no-verify -m x", "NOVERIFY"),
    ("nice git commit --no-verify -m x", "NOVERIFY"),
    ("nohup git commit -n -m x", "NOVERIFY"),
    ("sudo -u root git commit --no-verify -m x", "NOVERIFY"),
    ("env GIT_DIR=/x git commit --no-verify -m x", "NOVERIFY"),
    # 配對：放寬前綴不得把正常形態變成誤擋——誤擋比漏擋更糟，
    # 因為它會讓人把整道閘關掉。
    ("env git commit -m x", "COMMIT"),
    ("sudo git commit -m 'fix: x'", "COMMIT"),
    ("git commit -Sjohn -m x", "COMMIT"),
    ('echo "sudo git commit --no-verify" > note.txt', "SKIP"),
    ("sudo apt install git", "SKIP"),
])
def test_w35_command_wrappers_are_still_a_commit(cmd, expect):
    """W35：`env`／`sudo`／`nice`／`nohup` 包裝的 commit 仍要被判定。"""
    assert wiring_gate.classify(_bash(cmd)) == expect


def test_w35b_an_env_wrapper_still_hands_its_assignments_to_the_probe():
    """W35b：`env FOO=1 git commit` 的賦值必須進得了 env 前綴。

    放寬前綴時最容易踩的坑：把 `env` 排除在捕捉群組之外，賦值就跟著被排除，
    探測子行程於是拿**真 repo** 的設定去解析一個指向別處的 commit——
    答錯的方向是放行。所以整段前綴用同一個群組吃下來，再由 `ENV_ASSIGN_RE`
    挑出賦值（`sudo`、`-u root` 會被它忽略）。
    """
    invocations = wiring_gate.commit_invocations(
        "env GIT_DIR=/tmp/elsewhere/.git git commit -m x")
    assert len(invocations) == 1, invocations
    env = wiring_gate.git_env_prefix(invocations[0][2], invocations[0][0])
    assert env.get("GIT_DIR") == "/tmp/elsewhere/.git", env


def test_w36_git_common_dir_redirects_the_hook_and_must_be_denied(tmp_path):
    """W36：`GIT_COMMON_DIR` 是第七條改道通道，而它零覆蓋。

    `keep` 裡有這個名字，卻沒有任何一條測試單獨盯著它：把它從 `keep` 拿掉，
    89 條 wiring 測試全綠（2026-09-06 突變實測；W30 只咬得住 `GIT_DIR`）。

    先量測再斷言——hooks 住在 common dir，所以指到一份**剝掉 hooks 的同一份
    `.git`**，commit 照樣成立而 pre-commit 一次都沒跑（實測 git 2.53.0）。
    配對是第二半：指回自己的 `.git` 是 worktree 的正常寫法，不得誤擋。
    """
    repo = _wired_repo_with_sentinel(tmp_path / "r")
    stripped = tmp_path / "r" / "nohooks.git"
    shutil.copytree(str(repo / ".git"), str(stripped))
    os.remove(str(stripped / "hooks" / "pre-commit"))

    assert not _commit_with(repo, (), {"GIT_COMMON_DIR": str(stripped)}), \
        "前置不成立：GIT_COMMON_DIR 沒有真的讓 hook 不跑，這條測不到東西"

    deny = _run_gate(_bash("GIT_COMMON_DIR=%s git commit -m x" % stripped), repo)
    assert _is_deny(deny), "GIT_COMMON_DIR 改道到沒有 hooks 的地方，卻沒被擋"

    allow = _run_gate(
        _bash("GIT_COMMON_DIR=%s git commit -m x" % (repo / ".git")), repo)
    assert not _is_deny(allow), "指回自己的 .git 是正常寫法，卻被誤擋"


def test_w37_a_second_commit_on_the_line_is_judged_on_its_own_repo(tmp_path):
    """W37：一列裡有多個 commit 時，每一個都要用**自己的** repo 判定。

    `classify` 掃全部 segment 找 `--no-verify`，而 `main` 原本只拿
    `invocations[0]` 決定 repo 與 opt-in。兩邊範圍不一致，於是第一個 commit
    指向未 opt-in 的 repo 時，`not declared` 的早退把後面那個真正的
    `--no-verify` 連同判定一起丟掉。實測（2026-09-06 抗辯，pristine 4435f9a）：

        git commit -am x --no-verify                          → DENY
        git -C vendor commit -m bump && git commit -am x -nv  → **ALLOW**
        git -C vendor status && git commit -am x --no-verify  → DENY

    107 條測試全綠，因為每一條 `--no-verify` 案都斷言在 `classify` 上，而
    `classify` 是對的——沒有一條把整支 gate 端到端餵一條**多個 commit** 的
    指令列。最接近的 W8（`git -C /other status && git commit -n`）用的是
    `status`，它不產生 commit invocation，所以 `[0]` 還是真的那個。

    第三個案例是對照組，用來分辨「修好了」與「什麼都擋」。
    """
    repo = _git_repo(tmp_path / "r", declare=True, precommit=(
        "#!/bin/sh\n# runs .claude/wiring-guards\nexit 0\n"))
    _git_repo(tmp_path / "r" / "vendor", declare=False)   # 沒有 opt-in

    nv = "--no-" + "verify"
    bare = _run_gate(_bash("git commit -am x %s" % nv), repo)
    assert _is_deny(bare), "前置不成立：裸的 --no-verify 就沒擋，這條測不到東西"

    hidden = _run_gate(
        _bash("git -C vendor commit -m bump && git commit -am x %s" % nv), repo)
    assert _is_deny(hidden), (
        "前面掛一個指向未 opt-in repo 的 commit，後面的 --no-verify 就免罰了")

    control = _run_gate(_bash("git -C vendor status && git commit -am x %s" % nv), repo)
    assert _is_deny(control), "對照組：status 不產生 commit invocation，仍應擋"


def test_w38_an_amend_in_an_unwired_repo_is_still_caught(tmp_path):
    """W38：`--amend` 不再是接線檢查的豁免。

    `classify` 原本對整列都是 amend 的指令回 SKIP，而 `main` 在 SKIP 就 return
    ——於是一個 opt-in 卻沒接線的 repo，`git commit -m x` 被擋、
    `git commit --amend -m x` 放行。豁免沒有留下任何理由，1.2.0 以來就是這樣。

    前提先量過：`git commit --amend --no-edit` 與 `--amend -m` **兩種寫法都會
    執行 pre-commit**（git 2.53.0，哨兵印出 SENTINEL_RAN），所以那次 amend
    同樣是「守衛一次都沒跑」的 commit，正是 W2 要抓的病。

    配對是第二半：接線正確的 repo 用 amend **不得**被擋，否則這個修法會把
    一個極常見的動作變成永遠過不去，而那種閘會被整個關掉。
    """
    unwired = _git_repo(tmp_path / "u", declare=True)     # opt-in 但沒有 pre-commit
    assert _is_deny(_run_gate(_bash('git commit -m "x"'), unwired)), \
        "前置不成立：沒接線的 repo 連一般 commit 都沒擋"
    assert _is_deny(_run_gate(_bash('git commit --amend -m "x"'), unwired)), \
        "沒接線的 repo 用 --amend 就免罰了"

    wired = _git_repo(tmp_path / "w", declare=True, precommit=(
        "#!/bin/sh\n# runs .claude/wiring-guards\nexit 0\n"))
    assert not _is_deny(_run_gate(_bash('git commit --amend --no-edit'), wired)), \
        "接線正確的 repo 用 --amend 被誤擋——誤擋比漏擋更糟"


_NV = "--no-" + "verify"


@pytest.mark.parametrize("cmd,want_deny,label", [
    # 認不出來 → 以前回 SKIP → 無條件放行。實測 `timeout 60 git commit -m x
    # --no-verify` 真的產出 commit、守衛一次都沒跑、gate 一聲不吭。
    ("timeout 60 git commit -m x %s" % _NV, True, "timeout 包裝"),
    ("winpty git commit -m x %s" % _NV, True, "winpty 包裝（Git for Windows 預設安裝）"),
    ("setsid git commit -m x %s" % _NV, True, "setsid 包裝"),
    # bash 的 ANSI-C quoting 不在 VALUE 的三種寫法裡，於是連「這是一次 commit」
    # 都認不出來，而 fail-closed 兜底原本掛在早退的下游。
    ("git -c core.hooksPath=$'/tmp/a b' commit -m x", True, "$'…' 包住的 hooksPath"),
    ("git -c core.hooksPath=$'/tmp/no such\ndir' commit -m x", True, "$'…' 帶換行"),
    # ── 配對：以下每一條都**必須仍然放行**。少了它們，一個「認不出來就全擋」
    # 的兜底也會全綠，而那會讓人把整道閘關掉。
    ('git commit -m "fix: x"', False, "正常 commit"),
    ('git commit -m "never use %s"' % _NV, False, "訊息裡寫到那個旗標"),
    ('echo "git commit %s is bad"' % _NV, False, "引號裡的 git commit 不是 commit"),
    ("git log --grep commit --oneline -5", False, "唯讀 git log 也有 git 與 commit"),
    ('grep -rn "git commit %s" docs/' % _NV, False, "搜原始碼"),
    ("git config --get core.hooksPath", False, "讀 hooksPath 不是設定它"),
])
def test_w39_a_commit_the_gate_cannot_parse_fails_closed(tmp_path, cmd, want_deny, label):
    """W39：解析不出來的 commit 不得等於放行。

    這道閘的檔頭寫著「偵測不到就擋」，而那個 fail-closed 兜底
    （`unaccounted_hookspath`）掛在 `main` 的 SKIP 早退**下游**——也就是說
    「認不出來就擋」原本只適用於「已經被認出來的那些」。兩條實測繞道：
    外部包裝器（`timeout`／`winpty`／`setsid`…，列舉永遠慢一步）與 bash 的
    `$'…'` 引號。

    兜底的範圍刻意收窄成這道閘真正保護的兩件事（跳過 hook 的旗標、hooksPath），
    靠的是**引號遮蔽**分辨「裸的 git commit」與「引號裡的那串字」。六條配對案例
    就是這個收窄的驗收：全擋的兜底過不了它們。
    """
    repo = _git_repo(tmp_path, declare=True, precommit=(
        "#!/bin/sh\n# runs .claude/wiring-guards\nexit 0\n"))
    out = _run_gate(_bash(cmd), repo)
    assert _is_deny(out) is want_deny, (
        "%s：預期 %s，實際 %s" % (label, "DENY" if want_deny else "ALLOW",
                              "DENY" if _is_deny(out) else "ALLOW"))


def test_w39b_the_fallback_only_applies_to_repos_that_opted_in(tmp_path):
    """W39b：兜底同樣只管 opt-in 的 repo。

    這道閘是純 opt-in 的——沒有宣告檔的 repo 不該被擋下任何 commit。新增的
    fail-closed 兜底若忘了這一條，會變成對全世界的 repo 都生效。
    """
    plain = _git_repo(tmp_path, declare=False)
    out = _run_gate(_bash("timeout 60 git commit -m x %s" % _NV), plain)
    assert not _is_deny(out), "沒有 opt-in 的 repo 被兜底擋了"
