# -*- coding: utf-8 -*-
"""接線閘的**行為預言機**：判準是 git 真的做了什麼，不是我寫下來的期望值。

驗收項目清單：
  O1 生成的指令形狀逐一真的執行，凡「commit 成立而守衛沒跑」的一律要被擋
  O2 O1 的配對：守衛真的跑了的，一律不得被擋（誤擋比漏擋更糟）
  O3 語料本身要有鑑別力——必須真的含有一批**有效的**繞道，否則 O1 是空的

執行命令：
  cd <repo> && python -m pytest tests/test_wiring_oracle.py -v
  完整交叉展開（120 條、實測 56~62 秒）：加 --sweep

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-09-06 22:1x GMT+8）
══════════════════════════════════════
來由：使用者問「是不是該做通用測試，而不是針對某個版本的測試」。實查現況——
283 條測試裡只有 13 條（5%）用「真的跑起來再看結果」當預言機，其餘 270 條驗的
是我寫下來的期望值。那正是為什麼：拿今天的測試去跑 1.4.3 會紅 147 條，拿 1.4.3
的測試來跑今天的程式會紅 25 條——**兩套都是版本形狀的，不是不變量形狀的**，
所以那兩個數字都不代表品質差異。

本檔換一個預言機：**在拋棄式 repo 裡真的執行那條指令**，觀察 commit 有沒有成立、
哨兵 pre-commit 有沒有留下痕跡，再由這兩個事實導出「這條該不該被擋」。閘完全
不參與定義什麼叫正確，所以我列舉不到的寫法只要**真的有效**就會被抓到。

⚠ 預言機自己錯了三次才可用，逐條記在下面，因為預言機錯了它產生的數字全是垃圾：
  ① 哨兵 hook 只在**註解**裡提到宣告檔 → 閘正確地擋下每一條，而我記成「誤擋 52 條」
  ② repo 沒有初始 commit → 45 條 `--amend` 根本沒跑起來，被記成「沒有 commit」
  ③ env 前綴用 subprocess 的環境傳，而閘只看得到指令列 → 8 條被記成「漏擋」
  另外必須有第三類「指令沒跑起來」並排除（`winpty` 在本機需要 tty），否則 23 條
  被誤記成誤擋——拿沒發生的事去判對錯不公平。

[關鍵量測值｜同一套 120 條語料、同一個預言機、同一台機器]
  1.4.3（已發佈 b28ea35）：實際繞過 92 條 → **漏擋 72 條**、誤擋 0
  HEAD（2026-09-06）    ：實際繞過 92 條 → **漏擋 0 條**、誤擋 0
  不列入判斷：24 條（指令在本機跑不起來）

✅ 已驗收（本檔涵蓋）
  O1／O2／O3，全部驅動真實的 git 與真實的 hook 檔
⏳ 待驗收（本檔未涵蓋）
  維度只有五個（包裝器／旗標／全域選項／env 前綴／引號）。git 改道 hooks 的
  途徑若還有第六種而我沒把它放進生成器，這裡一樣看不到——差別在於**新增一個
  維度就會涵蓋它的所有組合**，而不是新增一條個案。解鎖條件＝發現新途徑時把它
  加進 `_dimensions()`，不是加一條測試。
  目標閘與驗證閘還沒有對應的預言機（它們的真相分別是真實 transcript 回放與
  「真的改了碼、真的沒跑測試」）。解鎖條件＝本檔的做法穩定之後照樣搬過去。
"""
import itertools
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(ROOT, ".claude", "hooks", "wiring_gate.py")
NV = "--no-" + "verify"


def _sh(cmd, cwd):
    env = dict(os.environ)
    env.setdefault("GIT_AUTHOR_NAME", "t")
    env.setdefault("GIT_AUTHOR_EMAIL", "t@t")
    env.setdefault("GIT_COMMITTER_NAME", "t")
    env.setdefault("GIT_COMMITTER_EMAIL", "t@t")
    return subprocess.run(["sh", "-c", cmd], cwd=cwd, env=env,
                          capture_output=True, encoding="utf-8",
                          errors="replace", timeout=60)


def _make_repo(path):
    """已 opt-in、pre-commit 是哨兵、而且**有初始 commit** 的 repo。

    初始 commit 不可省：沒有它 `git commit --amend` 根本沒有東西可以改寫，
    整個 amend 維度會靜靜地什麼都沒測到。
    哨兵在**可執行位置**引用宣告檔，不是註解——註解不算接線（W40）。
    """
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    os.makedirs(os.path.join(path, ".claude"), exist_ok=True)
    with open(os.path.join(path, ".claude", "wiring-guards"), "w",
              newline="") as fh:
        fh.write("true\n")
    hooks = os.path.join(path, ".git", "hooks")
    os.makedirs(hooks, exist_ok=True)
    with open(os.path.join(hooks, "pre-commit"), "w", newline="") as fh:
        fh.write("#!/bin/sh\n"
                 "test -f .claude/wiring-guards || exit 0\n"
                 "date > \"$(git rev-parse --git-dir)/../SENTINEL\"\n"
                 "exit 0\n")
    os.chmod(os.path.join(hooks, "pre-commit"), 0o755)
    with open(os.path.join(path, "f.txt"), "w", newline="") as fh:
        fh.write("x\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True,
                   capture_output=True)
    _sh("git commit %s -q -m base" % NV, str(path))
    marker = os.path.join(path, "SENTINEL")
    if os.path.exists(marker):
        os.remove(marker)
    with open(os.path.join(path, "f.txt"), "a", newline="") as fh:
        fh.write("y\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True,
                   capture_output=True)


def _dimensions(tmp_root):
    """五個維度。新增一條改道途徑時加在這裡，它的所有組合就都被涵蓋。"""
    empty = os.path.join(tmp_root, "emptyhooks")
    os.makedirs(empty, exist_ok=True)
    cfg = os.path.join(tmp_root, "cfg")
    with open(cfg, "w", newline="") as fh:
        fh.write("[core]\n\thooksPath = %s\n" % empty.replace("\\", "/"))
    e = empty.replace("\\", "/")

    wrappers = [("bare", "")]
    for name, form in (("command", "command "), ("env", "env "),
                       ("timeout", "timeout 60 "), ("nice", "nice "),
                       ("winpty", "winpty ")):
        if shutil.which(name):
            wrappers.append((name, form))

    flags = [("none", ""), ("--no-verify", " " + NV), ("-n", " -n"),
             ("--amend+nv", " --amend " + NV)]

    channels = [
        ("none", "", {}),
        ("-c", ' -c core.hooksPath="%s"' % e, {}),
        ("$'…'", " -c core.hooksPath=$'%s'" % e, {}),
        ("--config-env", " --config-env=core.hooksPath=FB_HP", {"FB_HP": e}),
        ("GIT_CONFIG_COUNT", "", {"GIT_CONFIG_COUNT": "1",
                                  "GIT_CONFIG_KEY_0": "core.hooksPath",
                                  "GIT_CONFIG_VALUE_0": e}),
        ("GIT_CONFIG_GLOBAL", "", {"GIT_CONFIG_GLOBAL": cfg.replace("\\", "/")}),
    ]
    return wrappers, flags, channels


def _corpus(tmp_root, full):
    wrappers, flags, channels = _dimensions(tmp_root)
    if full:
        combos = itertools.product(wrappers, flags, channels)
    else:
        # 預設語料：每個維度的每一個值至少出現一次，但不做完整交叉展開
        # ——完整展開 120 條實測 56~62 秒，會讓全套時間翻倍，而慢的測試會被跳過。
        base_w, base_c = wrappers[0], channels[0]
        # ⚠ 這一組展開實際是 `len(flags) + len(channels) + len(wrappers)` 列，
        # 而且會重複兩列（`bare|none|none` 與 `bare|--no-verify|none` 各出現兩次）。
        # 本機 15 列、相異 13 列——我在 commit 訊息與檔頭寫成「30 條」，錯了。
        # 更要緊的是 wrappers 由 `shutil.which` 決定，**一台少裝幾個工具的機器上
        # 語料會靜默縮水**，所以下面 O3 除了「有幾條有效繞道」之外，還要斷言
        # 維度本身沒有塌掉。
        # ⚠ 設定通道那一列必須配**沒有旗標**的 commit，不能配 `--no-verify`。
        # 第一版配了 `--no-verify`，於是每一條都先被旗標判定接住，通道的邏輯
        # 一次都沒有被單獨考驗——實測把 fail-closed 兜底整個拿掉、把
        # `--config-env` 的鏡射打斷，這三條測試**照樣全綠**（2026-09-06 自查）。
        # 語料的維度要能各自獨立地觸發，否則交叉展開只是把同一件事測很多次。
        # 每個包裝器**兩種身分各出現一次**：配 `--no-verify`（會繞道，考驗漏擋）
        # 與配裸 commit（守衛會跑，考驗誤擋）。
        # ⚠ 第一版只有前者。於是「守衛真的跑了」的列只剩 2 條、而且是同一條
        # 指令，O2（誤擋那一半）等於只由一種形狀在守——把「有包裝器就擋」這種
        # 過度收緊注入閘裡，預設語料**全綠**，只有 `--sweep` 抓得到
        # （2026-09-06 正確性鏡頭實測）。這與同一個 commit 宣稱已修好的通道維度
        # 是**同一類**，我只掃了一處。
        combos = ([(base_w, f, base_c) for f in flags]
                  + [(base_w, flags[0], c) for c in channels]
                  + [(w, flags[1], base_c) for w in wrappers]
                  + [(w, flags[0], base_c) for w in wrappers])
    out = []
    for (wn, wf), (fn, ff), (cn, cf, cenv) in combos:
        prefix = "".join("%s=%s " % (k, v) for k, v in sorted(cenv.items()))
        out.append(("%s|%s|%s" % (wn, fn, cn),
                    '%s%sgit%s commit%s -m "probe"' % (prefix, wf, cf, ff)))
    return out


def _observe(repo, cmd):
    """真相：(有沒有產生 commit, 守衛有沒有跑)。

    用 HEAD 的 sha 比對而不是數 commit 數——`--amend` 會改寫而不增加數量。
    """
    def head():
        r = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           capture_output=True, encoding="utf-8")
        return r.stdout.strip() if r.returncode == 0 else ""
    before = head()
    _sh(cmd, str(repo))
    return head() != before, os.path.exists(os.path.join(repo, "SENTINEL"))


def _gate_denies(cmd, cwd):
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    r = subprocess.run([sys.executable, GATE], input=json.dumps(payload),
                       cwd=str(cwd), capture_output=True, encoding="utf-8",
                       errors="replace", timeout=60)
    assert r.returncode == 0, "gate 不得非零退出（fail-open 契約）：%s" % r.stderr
    if not r.stdout.strip():
        return False
    return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def _run_corpus(tmp_path, full):
    rows = []
    for i, (label, cmd) in enumerate(_corpus(str(tmp_path), full)):
        repo = tmp_path / ("r%d" % i)
        _make_repo(repo)
        committed, sentinel = _observe(repo, cmd)
        rows.append((label, cmd, committed, sentinel, _gate_denies(cmd, repo)))
    return rows


@pytest.fixture(scope="module")
def rows(tmp_path_factory, pytestconfig):
    """整組語料只跑一次。

    ⚠ 三條測試原本各自呼叫 `_run_corpus`，於是同一批語料**建三次拋棄式 repo、
    跑三次 git、跑三次 gate**——O1／O2／O3 只是同一組觀測的三種投影
    （2026-09-06 簡潔性鏡頭指出）。改成 module fixture 之後鑑別力一分不減，
    預設路徑省掉三分之二的執行時間。

    `--sweep` 從「多跑一條測試」變成「把語料放寬」：加了旗標，O1 與 O2 檢驗的
    就是完整的 120 條，而不是另外跑一條只檢查一半的測試。
    """
    return _run_corpus(tmp_path_factory.mktemp("oracle"),
                       full=pytestconfig.getoption("--sweep"))


def test_o3_the_corpus_actually_contains_working_bypasses(rows, tmp_path):
    """O3：語料必須真的含有一批**有效的**繞道，否則 O1 是空的。

    這是本檔的前置條件：如果生成的指令一條都繞不過守衛，「全部都被擋下」這句話
    什麼都不證明。斷言的是 git 的實際行為，與閘無關。
    """
    bypasses = [r for r in rows if r[2] and not r[3]]
    ran = [r for r in rows if r[3]]
    assert len(bypasses) >= 5, (
        "語料裡只有 %d 條真的繞過守衛，鑑別力不足：%s"
        % (len(bypasses), [r[0] for r in rows[:5]]))
    assert ran, "語料裡沒有任何一條讓守衛真的跑起來——O2 會變成空的"
    # 維度不得靜默塌掉：包裝器由 `shutil.which` 偵測，一台少裝工具的機器上
    # wrappers 會掉到 1，語料只剩 11 列，而上面那個 `>= 5` **照樣過**——光靠
    # 設定通道那幾列就滿足了。那時「全部擋下」保護的是一個縮水的語料，而沒有
    # 任何紅燈。這是本 repo 自己在別處補過的「守衛正在保護空氣」那一類。
    wrappers, flags, channels = _dimensions(str(tmp_path))
    assert len(wrappers) >= 3 and len(channels) >= 5, (
        "語料的維度塌了：包裝器 %d 種、設定通道 %d 種——這台機器缺工具，"
        "量出來的『全部擋下』不代表什麼" % (len(wrappers), len(channels)))


def test_o1_every_working_bypass_is_denied(rows):
    """O1：commit 成立而守衛沒跑的，一律要被擋。

    判準完全由 git 的實際行為導出，閘不參與定義。同一套語料在已發佈的 1.4.3
    上實測**漏擋 72/92**，在 HEAD 上 0/92。
    """
    missed = [(r[0], r[1]) for r in rows if (r[2] and not r[3]) and not r[4]]
    assert not missed, (
        "以下指令真的產生了 commit 而守衛一次都沒跑，閘卻放行：\n%s"
        % "\n".join("  %-28s %s" % m for m in missed))


def test_o2_a_commit_whose_guards_ran_is_not_denied(rows):
    """O2：O1 的配對——守衛真的跑了的，不得被擋。

    只有 O1 的話，一個「什麼都擋」的閘會全綠，而那會讓人把整道閘關掉。
    ⚠ 「指令根本沒跑起來」的第三類必須排除：`winpty` 在本機需要 tty，既沒
    commit 也沒哨兵，拿它去判「不該擋」會憑空製造 23 條假的誤擋。
    """
    wrong = [(r[0], r[1]) for r in rows if r[3] and r[4]]
    assert not wrong, (
        "以下指令的守衛真的跑了，閘卻擋下來（誤擋比漏擋更糟）：\n%s"
        % "\n".join("  %-28s %s" % w for w in wrong))
