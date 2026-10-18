# -*- coding: utf-8 -*-
"""pre-commit 薄殼與安裝腳本的驗收——薄殼讀的是 Fable main 上已 commit 的 runner。

對應 INSTALL.md 步驟 10（接線閘門的 pre-commit 安裝）。薄殼
`.claude/hooks/precommit_shell.sh` 不是 runner 的複本：它在每次 commit 時從
Fable 的 `refs/heads/main` 讀 `.claude/hooks/wiring_runner.sh` 並執行，所以 commit 進
Fable main 就是部署；安裝腳本 `scripts/install_precommit.sh` 負責把薄殼放進一個 repo。

驗收項目（R = 薄殼行為；I = 安裝腳本；M = 範本來源；X = 檔案本身）：
  R01 紅守衛擋 commit（rc=1）；R02 綠守衛放行（rc=0）；R03 紅 + ALLOW_UNWIRED=1 放行（rc=0）
  R04/R05 linked worktree 紅擋／綠放，且被保護 repo 自己的 decoy runner 不得被執行
  R06 `--git-dir`/`--work-tree` 形態的 commit 仍擋紅
  R07 Fable 工作樹的未 commit 改動（換成 exit 0）不得生效，吃的是 main 上的版本
  R08 另一分支有弱化 runner、且有 tag 叫 main：仍讀 refs/heads/main
  R09/R10 Fable 不存在：紅擋、ALLOW_UNWIRED 放行
  R11/R12/R13 main 上的 runner 有語法錯誤：紅擋、ALLOW_UNWIRED 放行；修好後綠放行
  R14 F 指向被保護 repo 內一個沒有 .git 的目錄：不得退而讀到被保護 repo 的 runner
  R15 沒有宣告檔且 Fable 不存在：照樣放行（opt-in 規則）
  R16 紅訊息點名 INSTALL.md step 10 與 ALLOW_UNWIRED；R17 真正的紅守衛不得被說成 F 設錯
  B01/B02 Fable main 上的 runner 被改成「什麼都沒做也回 0」（空檔／空白／只有 shebang 加註解／
    `:`／`exit 0`／只有標記註解／標記加 exit 0／只往一般 stdout 印回報字串）：守衛 false 與 true
    各一次，commit 必須被擋（rc=1，訊息 "runner did not confirm guard execution"）；
    ALLOW_UNWIRED=1 時 rc=0 且留下 "[wiring] RED" 與 "ALLOW_UNWIRED=1" 訊息
  B03-B08 配對（正常 runner 下必須仍然做得到）：B03 全綠可 commit；B04 多條守衛中後段紅會擋；
    B05 讀 stdin 的守衛不卡住、後面的守衛照跑；B06 宣告檔最後一行沒有換行照跑；
    B07 零守衛＝runner 既有規定的紅（"declares no guards"），ALLOW_UNWIRED=1 放行且薄殼留下
    "runner did not confirm" 紅；B08 守衛往 fd 3 偽造回報寫不進去（runner 對守衛關 fd 3）
  I01 取代本 kit 舊複本（runner 複本／舊薄殼），守衛只跑一次、舊檔備份
  I02 連裝兩次不覆蓋第一份備份，備份檔名 .bak.YYYYMMDD-HHMMSS
  I10 路徑含 " $ ` 拒絕且不寫任何檔；I03 非本 kit 的 hook 拒絕且不動；I04 使用者 hook 內嵌
  舊 runner 也拒絕；I05/I06/I16 core.hooksPath（相對／絕對／空字串）拒絕；I08 備份失敗不取代
  I09 訊息點名備份路徑；I07 路徑（含 &；Windows 反斜線路徑經安裝腳本轉成 `/`，測試比的是
  posix 形態）寫入 F=；I11 相對路徑存成絕對路徑
  I12 非 git clone（ZIP）拒絕；I13 repo 外執行拒絕；I14 pre-commit 是目錄拒絕
  I15 沒有 hooks 目錄的 repo 可裝且紅守衛擋得住；I17 pre-commit 是 symlink 拒絕
  M18 範本取自 Fable main，不取工作樹未 commit 的改動；M19 Fable 在別的分支，仍取 main
  X01 範本只有一個 @FABLE@ 且是 LF；X02 安裝腳本沒有範本覆寫分支

執行命令（repo 根目錄）：
  python -m pytest tests/test_precommit_shell.py -q -p no:cacheprovider

測試自建「假 Fable」repo（git init -b main，只放本 worktree 的 runner 與薄殼），
不 clone、不讀寫任何真實 Fable／Finzo 目錄。

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-10-18 11:20 GMT+8）
══════════════════════════════════════
對應規劃書：INSTALL.md 步驟 10；CHANGELOG [1.6.0] 的 pre-commit 薄殼條目
執行命令：python -m pytest tests/test_precommit_shell.py -q -p no:cacheprovider
最後執行：2026-10-18 11:20 → 80 passed ✅（約 59 秒）

[關鍵量測]
  TDD 紅燈（薄殼尚未要求 runner 回報）：B01/B02 共 32 failed（16 種 runner×守衛組合各兩條：
    B01 例 `exit0: rc=0 want=1`；B02 例 `assert ('ALLOW_UNWIRED=1' in '')`），B03-B08 的 6 條
    配對在舊薄殼本來就綠（passed）——它們守的是「新規則不得把正常流程也擋掉」
  綠燈：80 passed（42 + B01 16 + B02 16 + B03-B08 6）
  突變（逐一改壞後跑對應測試，必須紅；改回後綠）：
    runner 守衛執行處拿掉 `3>&-` → B08 failed；
    runner 拿掉 `guards_run -gt 0` → B07 failed；
    薄殼刪掉 `[ "$proof" = ... ]` 那行 → B01 failed（3 條 exit0／echo_receipt_stdout 變體）；
    runner 不出具回報（printf 換成 `:`）→ B03 failed
  升級實跑（拋棄式 repo，已清除）：v1.5.0 的 runner 複本當 pre-commit → 紅擋 rc=1／綠過 rc=0、
    守衛跑 1 次；以 scripts/install_precommit.sh 升級 → 舊複本備份為 pre-commit.bak.<時間>、
    紅擋 rc=1／綠過 rc=0（守衛跑 1 次）；之後在假 Fable main 改 runner 立即生效；
    把假 Fable main 的 runner 掏空 → 綠守衛也被擋（"runner did not confirm guard execution"）

【歷史紀錄】以下為 2026-10-14 23:04 的舊紀錄（42 passed），保留原文不改：

[關鍵量測·歷史]
  TDD 紅燈（薄殼與安裝腳本尚未建立）：2 failed, 1 passed, 39 errors（fixture 讀不到 precommit_shell.sh）
  綠燈：42 passed（R17 + I21 + M2 + X2；I01/I07 各參數化 2 格、I10 參數化 3 格）；原生 symlink 可建，I17 未 skip
  突變（舊讀法 `git -C "$F" ... main:<path>` 的薄殼）：9 failed, 33 passed
    翻紅：R04 R05 R06 R08 R14 R15 R16 I01[2] M19——即 linked worktree／--git-dir／同名 tag 等
    git 匯出環境與歧義情境；舊讀法在這些情境讀到被保護 repo 或錯誤的 ref
  全套 tests/：498 passed, 3 skipped（基準 456 passed, 3 skipped，+42）

✅ 已驗收（本檔涵蓋）
  B01-B08 → 8 種被掏空的 runner×守衛 false／true：rc=1 且訊息含 "runner did not confirm guard
    execution"；ALLOW_UNWIRED=1 rc=0 且留下訊息；正常 runner 下 B03-B06 rc 與 .runs 計數如預期
  R01-R17 → 紅 rc=1／綠 rc=0／ALLOW_UNWIRED rc=0，且 DECOY-RAN 從未出現在輸出
  I01-I17 → 拒絕案例 rc≠0 且 hook 內容或目錄零變動；允許案例 F= 行與預期路徑逐字相等（忽略大小寫）
  M18/M19 → 範本取自 main：工作樹的 WIP-MARK、另一分支的 SIDE-MARK 都不會被裝進 hook
⏳ 待驗收（本檔未涵蓋）
  真實 Fable 的升級路徑：本檔與 2026-10-18 的升級實跑都只用假 Fable（從本分支 clone），
    不碰真實目錄；解鎖條件＝本分支合併進 Fable main 並經使用者點頭後，對真實 Fable 的
    clone 再實跑安裝腳本一次（升級實跑本身已在拋棄式 repo 完成，見上方 2026-10-18 紀錄）
  BROKEN_RUNNERS 之外的蓄意造假：runner 本身可以直接往 fd 3 寫回報——回報只證明 runner 走到
    結尾並跑過至少一條守衛，信任的是經審查進入 Fable main 的程式；解鎖條件＝無（設計上的界線）
  macOS／Linux：只在 Windows Git Bash 驗過；解鎖條件＝有該平台環境可跑本檔
  I07 路徑大小寫以 casefold 比較（Windows 路徑不分大小寫）；大小寫敏感檔案系統上的行為未驗
"""
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_SRC = REPO_ROOT / ".claude" / "hooks" / "wiring_runner.sh"
SHELL_SRC = REPO_ROOT / ".claude" / "hooks" / "precommit_shell.sh"
INSTALLER = (REPO_ROOT / "scripts" / "install_precommit.sh").as_posix()

# git 會把這些匯出給 hook；測試行程不得帶著它們，否則會讀到外層 repo。
_STRIP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
          "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "ALLOW_UNWIRED")
_IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def _px(p):
    return Path(p).as_posix()


class Box:
    """一個測試的隔離環境：乾淨 env、自帶身分的 git、讀寫位元組的小工具。"""

    def __init__(self, root):
        self.root = Path(root)
        home = self.root / "home"
        home.mkdir()
        (home / "gitconfig").write_bytes(b"[core]\n\tautocrlf = false\n")
        self.env = {k: v for k, v in os.environ.items() if k not in _STRIP}
        self.env["HOME"] = str(home)
        self.env["GIT_CONFIG_GLOBAL"] = str(home / "gitconfig")

    def run(self, argv, cwd, env=None):
        e = dict(self.env)
        e.update(env or {})
        r = subprocess.run(argv, cwd=str(cwd), env=e, capture_output=True,
                           timeout=120)
        return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")

    def git(self, cwd, *args, env=None, check=True):
        rc, out = self.run(["git"] + _IDENT + list(args), cwd, env)
        if check:
            assert rc == 0, "git %s failed in %s: %s" % (args, cwd, out)
        return rc, out

    def sh(self, *args, cwd, env=None):
        return self.run(["sh"] + list(args), cwd, env)

    def install(self, fab, cwd, env=None):
        return self.sh(INSTALLER, str(fab), cwd=cwd, env=env)

    def commit(self, cwd, env=None, git_args=()):
        return self.git(cwd, *git_args, "commit", "-qm", "x", env=env, check=False)

    def attempt(self, cwd, guard, env=None, eol="\n"):
        """寫入宣告、改一個檔、commit；回 (rc, 輸出)。eol="" 即最後一行沒有換行。"""
        cwd = Path(cwd)
        (cwd / ".claude").mkdir(exist_ok=True)
        (cwd / ".claude" / "wiring-guards").write_bytes((guard + eol).encode())
        with open(cwd / "f", "ab") as fh:
            fh.write(b"x\n")
        self.git(cwd, "add", "-A")
        return self.commit(cwd, env=env)


def _thin_shell(fab):
    return SHELL_SRC.read_bytes().replace(b"@FABLE@", _px(fab).encode())


def _put_hook(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chmod(str(path), 0o755)


def _make_fable(box, name="fab"):
    """假 Fable：main 上有本 worktree 的 runner 與薄殼（已 commit）。"""
    f = box.root / name
    f.mkdir()
    box.git(f, "init", "-q", "-b", "main")
    hooks = f / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copyfile(str(RUNNER_SRC), str(hooks / "wiring_runner.sh"))
    shutil.copyfile(str(SHELL_SRC), str(hooks / "precommit_shell.sh"))
    box.git(f, "add", "-A")
    box.git(f, "commit", "-qm", "fake fable")
    return f


def _mk_repo(box, name):
    """被保護的 repo：宣告檔內容是會留下執行痕跡的守衛。"""
    r = box.root / name
    box.git(box.root, "init", "-q", str(r))
    (r / ".claude").mkdir()
    (r / ".claude" / "wiring-guards").write_bytes(b"echo x >> .runs\n")
    return r


@pytest.fixture
def box(tmp_path):
    return Box(tmp_path)


@pytest.fixture
def fab(box):
    return _make_fable(box)


@pytest.fixture
def prot(box, fab):
    """被保護的 repo p（含一支只會印 DECOY-RAN 的 runner 誘餌）、linked worktree、已裝薄殼。"""
    p = box.root / "p"
    box.git(box.root, "init", "-q", "-b", "main", str(p))
    hooks = p / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "wiring_runner.sh").write_bytes(b"#!/bin/sh\necho DECOY-RAN >&2\nexit 0\n")
    (p / ".claude" / "wiring-guards").write_bytes(b"false\n")
    box.git(p, "add", "-A")
    box.git(p, "commit", "-qm", "decoy")
    wt = box.root / "p_wt"
    box.git(p, "worktree", "add", "-q", str(wt), "-b", "wt")
    hook = p / ".git" / "hooks" / "pre-commit"
    _put_hook(hook, _thin_shell(fab))

    class P:
        pass
    o = P()
    o.p, o.wt, o.hook, o.fab = p, wt, hook, fab
    return o


def _expect(box, d, guard, want, env=None, label=""):
    rc, out = box.attempt(d, guard, env=env)
    assert "DECOY-RAN" not in out, "被保護 repo 的 runner 被執行了：" + out
    assert rc == want, "%s: rc=%s want=%s\n%s" % (label, rc, want, out)
    return out


# ──────────────────────────── R：薄殼行為 ────────────────────────────

def test_r01_red_guard_blocks(box, prot):
    _expect(box, prot.p, "false", 1)


def test_r02_green_guard_passes(box, prot):
    _expect(box, prot.p, "true", 0)


def test_r03_red_with_allow_unwired_passes(box, prot):
    _expect(box, prot.p, "false", 0, env={"ALLOW_UNWIRED": "1"})


def test_r04_linked_worktree_red_blocks(box, prot):
    _expect(box, prot.wt, "false", 1)


def test_r05_linked_worktree_green_passes(box, prot):
    _expect(box, prot.wt, "true", 0)


def test_r06_git_dir_form_commit_still_blocks_red(box, prot):
    p = prot.p
    (p / ".claude" / "wiring-guards").write_bytes(b"false\n")
    with open(p / "f", "ab") as fh:
        fh.write(b"y\n")
    box.git(p, "add", "-A")
    rc, out = box.git(p, "--git-dir=" + _px(p / ".git"), "--work-tree=" + _px(p),
                      "commit", "-qm", "y", check=False)
    assert rc == 1, out


def test_r07_fable_uncommitted_edit_is_not_what_runs(box, prot):
    (prot.fab / ".claude" / "hooks" / "wiring_runner.sh").write_bytes(b"#!/bin/sh\nexit 0\n")
    _expect(box, prot.p, "false", 1)


def test_r08_weak_runner_on_branch_and_tag_named_main(box, prot):
    f = prot.fab
    box.git(f, "checkout", "-qb", "side")
    (f / ".claude" / "hooks" / "wiring_runner.sh").write_bytes(b"#!/bin/sh\nexit 0\n")
    box.git(f, "commit", "-qam", "weak")
    box.git(f, "tag", "main")
    box.git(f, "checkout", "-q", "main")
    _expect(box, prot.p, "false", 1)


def test_r09_fable_missing_blocks(box, prot):
    _put_hook(prot.hook, _thin_shell(box.root / "nope"))
    _expect(box, prot.p, "false", 1)


def test_r10_fable_missing_with_allow_unwired_passes(box, prot):
    _put_hook(prot.hook, _thin_shell(box.root / "nope"))
    _expect(box, prot.p, "false", 0, env={"ALLOW_UNWIRED": "1"})


def _break_runner_on_main(box, fab):
    """在 runner 中段（迴圈內第一行指令）以 pattern 定位插入語法錯誤，並提交到 main。"""
    path = fab / ".claude" / "hooks" / "wiring_runner.sh"
    lines = path.read_bytes().split(b"\n")
    idx = [i for i, ln in enumerate(lines) if ln.startswith(b"    cmd=$(printf")]
    assert len(idx) == 1, "定位 pattern 應唯一命中迴圈內的 cmd= 行"
    lines.insert(idx[0], b"if then")
    path.write_bytes(b"\n".join(lines))
    box.git(fab, "commit", "-qam", "broken")


def test_r11_syntax_error_on_main_blocks_even_green_guard(box, prot):
    _break_runner_on_main(box, prot.fab)
    _expect(box, prot.p, "true", 1)


def test_r12_syntax_error_with_allow_unwired_passes(box, prot):
    _break_runner_on_main(box, prot.fab)
    _expect(box, prot.p, "true", 0, env={"ALLOW_UNWIRED": "1"})


def test_r13_main_repaired_green_passes(box, prot):
    _break_runner_on_main(box, prot.fab)
    _expect(box, prot.p, "true", 1)
    box.git(prot.fab, "reset", "-q", "--hard", "HEAD~1")
    _expect(box, prot.p, "true", 0)


def test_r14_f_is_non_repo_dir_inside_protected_repo(box, prot):
    nogit = prot.p / "vendor" / "fab_nogit"
    (nogit / ".claude" / "hooks").mkdir(parents=True)
    shutil.copyfile(str(RUNNER_SRC), str(nogit / ".claude" / "hooks" / "wiring_runner.sh"))
    _put_hook(prot.hook, _thin_shell(nogit))
    _expect(box, prot.p, "false", 1)


def test_r15_no_declaration_passes_even_with_fable_missing(box, prot):
    _put_hook(prot.hook, _thin_shell(box.root / "nope"))
    p = prot.p
    box.git(p, "rm", "-q", "--cached", ".claude/wiring-guards")
    os.remove(str(p / ".claude" / "wiring-guards"))
    with open(p / "f", "ab") as fh:
        fh.write(b"z\n")
    box.git(p, "add", "-A")
    rc, out = box.commit(p)
    assert rc == 0, out


def test_r16_red_message_names_the_fix_and_the_escape(box, prot):
    _put_hook(prot.hook, _thin_shell(box.root / "nope"))
    out = _expect(box, prot.p, "false", 1)
    assert re.search(r"INSTALL\.md step 10.*ALLOW_UNWIRED", out, re.S), out


def test_r17_real_red_guard_does_not_blame_f(box, prot):
    out = _expect(box, prot.p, "false", 1)
    assert "set F=" not in out, out


# ─────────── B：Fable main 上的 runner 被改成「什麼都沒做也回 0」 ───────────
#
# 薄殼只看 runner 的退出碼時，這些形態全部靜默放行。薄殼現在要求 runner 在正常
# 走到結尾、且至少跑過一條守衛時，把 FABLE_WIRING_V1_RAN 寫到 fd 3；沒收到就是紅。

_MARKER = b"# wiring_runner.sh \xe2\x80\x94 git pre-commit runner\n"
BROKEN_RUNNERS = {
    "empty": b"",
    "blank": b"   \n\n  \t\n",
    "shebang_comment": b"#!/bin/sh\n# anything here\n",
    "colon": b":\n",
    "exit0": b"exit 0\n",
    "marker_only": b"#!/bin/sh\n" + _MARKER,
    "marker_exit0": b"#!/bin/sh\n" + _MARKER + b"exit 0\n",
    # 回報字串印到一般 stdout，不是 fd 3：不得被當成回報
    "echo_receipt_stdout": b"#!/bin/sh\necho FABLE_WIRING_V1_RAN\nexit 0\n",
}


def _set_runner_on_main(box, fab, data):
    (fab / ".claude" / "hooks" / "wiring_runner.sh").write_bytes(data)
    box.git(fab, "commit", "-qam", "swap runner")


@pytest.mark.parametrize("guard", ["false", "true"])
@pytest.mark.parametrize("name", sorted(BROKEN_RUNNERS))
def test_b01_broken_runner_blocks_commit(box, prot, name, guard):
    _set_runner_on_main(box, prot.fab, BROKEN_RUNNERS[name])
    out = _expect(box, prot.p, guard, 1, label=name)
    assert "runner did not confirm guard execution" in out, out


@pytest.mark.parametrize("guard", ["false", "true"])
@pytest.mark.parametrize("name", sorted(BROKEN_RUNNERS))
def test_b02_broken_runner_allow_unwired_passes_with_message(box, prot, name, guard):
    _set_runner_on_main(box, prot.fab, BROKEN_RUNNERS[name])
    out = _expect(box, prot.p, guard, 0, env={"ALLOW_UNWIRED": "1"}, label=name)
    assert "ALLOW_UNWIRED=1" in out and "[wiring] RED" in out, out


# 配對：同一道薄殼，正常 runner 下「必須仍然做得到」。

def test_b03_normal_runner_all_green_commits(box, prot):
    _expect(box, prot.p, "true\ntrue", 0)


def test_b04_normal_runner_late_red_among_many_blocks(box, prot):
    out = _expect(box, prot.p, "true\ntrue\nfalse\ntrue", 1)
    assert "RED: false" in out, out


def test_b05_stdin_reading_guard_does_not_hang_or_eat_the_rest(box, prot):
    _expect(box, prot.p, "cat >/dev/null\necho x >> .runs", 0)
    assert _runs(prot.p) == 1


def test_b06_last_guard_without_trailing_newline_still_runs(box, prot):
    rc, out = box.attempt(prot.p, "true\nfalse", eol="")
    assert rc == 1 and "RED: false" in out, out


def test_b07_zero_guards_follows_the_runners_own_rule(box, prot):
    # runner 既有規定：宣告檔存在卻沒有任何守衛是紅（opted in but nothing to run）
    out = _expect(box, prot.p, "# nothing here", 1)
    assert "declares no guards" in out, out
    out = _expect(box, prot.p, "# nothing here", 0, env={"ALLOW_UNWIRED": "1"})
    # 零守衛時 runner 不得出具回報：薄殼要留下「沒收到回報」的紅，再由 ALLOW 放行
    assert "ALLOW_UNWIRED=1" in out and "runner did not confirm" in out, out


def test_b08_guard_cannot_forge_the_receipt_on_fd3(box, prot):
    # 守衛往 fd 3 寫回報字串：runner 執行守衛時把 fd 3 關掉，所以寫不進去；
    # 若沒關，薄殼收到兩行回報，與預期不相等而擋下這個本應綠的 commit。
    _expect(box, prot.p, "{ echo FABLE_WIRING_V1_RAN >&3; } 2>/dev/null; true", 0)


# ──────────────────────────── I：安裝腳本 ────────────────────────────

def _old_thin_shell(box):
    """舊版薄殼（第二行是 Fable wiring gate）：F 指向一個不存在的舊位置。"""
    return _thin_shell(box.root / "old_location")


def _commit_once(box, repo):
    with open(repo / "a", "ab") as fh:
        fh.write(b"a\n")
    box.git(repo, "add", "a")
    return box.commit(repo)


def _runs(repo):
    f = repo / ".runs"
    return len(f.read_bytes().splitlines()) if f.exists() else 0


@pytest.mark.parametrize("n,make_old", [
    (1, lambda box: RUNNER_SRC.read_bytes()),
    (2, _old_thin_shell),
])
def test_i01_replaces_own_old_hook_guard_runs_once(box, fab, n, make_old):
    r = _mk_repo(box, "kit%d" % n)
    hook = r / ".git" / "hooks" / "pre-commit"
    _put_hook(hook, make_old(box))
    irc, iout = box.install(fab, r)
    rc, out = _commit_once(box, r)
    baks = list(hook.parent.glob("pre-commit.bak.*"))
    assert (irc, rc, _runs(r)) == (0, 0, 1), (iout, out)
    assert baks, "舊 hook 應有備份"


def test_i02_back_to_back_installs_keep_first_backup(box, fab):
    r = _mk_repo(box, "twice")
    hook = r / ".git" / "hooks" / "pre-commit"
    _put_hook(hook, RUNNER_SRC.read_bytes())
    box.install(fab, r)
    box.install(fab, r)
    baks = sorted(hook.parent.glob("pre-commit.bak.*"))
    runner_copies = [b for b in baks
                     if b.read_bytes().split(b"\n")[1].startswith(b"# wiring_runner.sh")]
    bad = [b.name for b in baks if not re.fullmatch(r"pre-commit\.bak\.\d{8}-\d{6}", b.name)]
    assert len(runner_copies) == 1 and not bad, (len(runner_copies), bad)


def _clone_to(box, fab, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    box.git(box.root, "clone", "-q", str(fab), str(dest))
    return dest


@pytest.mark.parametrize("label", ["quote", "dollar", "backtick"])
def test_i10_path_with_special_char_refused_nothing_written(box, fab, label):
    r = _mk_repo(box, "q_" + label)
    if label == "quote":    # Windows 檔名不能含 "，只能給不存在的路徑
        arg = _px(box.root) + '/x/a"b/Fable'
    else:
        d = {"dollar": "$HOME", "backtick": "a`b"}[label]
        arg = str(_clone_to(box, fab, box.root / "x" / d / "Fable"))
    irc, out = box.install(arg, r)
    assert irc != 0 and not (r / ".git" / "hooks" / "pre-commit").exists(), out
    if label != "quote":
        assert "unsupported character" in out, out


def test_i03_foreign_hook_refused_untouched(box, fab):
    r = _mk_repo(box, "foreign")
    hook = r / ".git" / "hooks" / "pre-commit"
    hook.write_bytes(b"#!/bin/sh\necho mine\n")
    before = hook.read_bytes()
    irc, out = box.install(fab, r)
    assert irc != 0 and hook.read_bytes() == before, out


def test_i04_user_hook_with_old_runner_appended_refused(box, fab):
    r = _mk_repo(box, "appended")
    hook = r / ".git" / "hooks" / "pre-commit"
    tail = RUNNER_SRC.read_bytes().split(b"\n", 1)[1]
    hook.write_bytes(b"#!/bin/sh\necho my-own\n" + tail)
    before = hook.read_bytes()
    irc, out = box.install(fab, r)
    assert irc != 0 and hook.read_bytes() == before, out


def test_i05_core_hookspath_set_refused(box, fab):
    r = _mk_repo(box, "husky")
    (r / ".husky").mkdir()
    box.git(r, "config", "core.hooksPath", ".husky")
    irc, out = box.install(fab, r)
    assert irc != 0 and not (r / ".husky" / "pre-commit").exists(), out


def test_i06_absolute_hookspath_refused(box, fab):
    r = _mk_repo(box, "glob")
    gh = box.root / "globhooks"
    gh.mkdir()
    box.git(r, "config", "core.hooksPath", str(gh))
    irc, out = box.install(fab, r)
    assert irc != 0 and not list(gh.iterdir()), out


def test_i08_backup_failure_replaces_nothing(box, fab):
    r = _mk_repo(box, "bakfail")
    hook = r / ".git" / "hooks" / "pre-commit"
    _put_hook(hook, RUNNER_SRC.read_bytes() + b"# EDIT2\n")
    fb = box.root / "fakebin"
    fb.mkdir()
    _put_hook(fb / "cp", b"#!/bin/sh\nexit 1\n")
    irc, out = box.install(fab, r, env={"PATH": str(fb) + os.pathsep + box.env.get("PATH", "")})
    assert irc != 0 and b"EDIT2" in hook.read_bytes(), out


def test_i09_replacement_names_backup_path(box, fab):
    r = _mk_repo(box, "msg")
    _put_hook(r / ".git" / "hooks" / "pre-commit", RUNNER_SRC.read_bytes())
    irc, out = box.install(fab, r)
    assert irc == 0 and re.search(r"backed up to .*pre-commit\.bak\.", out), out


def _f_lines(repo):
    return [ln for ln in (repo / ".git" / "hooks" / "pre-commit").read_text(
        encoding="utf-8").splitlines() if ln.startswith("F=")]


@pytest.mark.parametrize("style", ["amp_dir", "backslash"])
def test_i07_path_written_exactly_as_F(box, fab, style):
    r = _mk_repo(box, "p_" + style)
    if style == "amp_dir":   # 含 & 的目錄：sed 取代字串裡 & 有特殊意義
        arg = _clone_to(box, fab, box.root / "R&D" / "Fable")
    else:                    # Windows 反斜線路徑
        arg = fab
    irc, out = box.install(str(arg), r)
    want = 'F="%s"' % _px(arg)
    got = _f_lines(r) if irc == 0 else []
    assert irc == 0 and len(got) == 1 and got[0].casefold() == want.casefold(), (irc, got, want, out)


def test_i11_relative_path_stored_absolute(box, fab):
    r = _mk_repo(box, "rel")
    box.git(r, "commit", "-q", "--allow-empty", "-m", "base")
    sub = _clone_to(box, fab, box.root / "R&D" / "Fable")
    irc, out = box.install("../R&D/Fable", r)
    want = 'F="%s"' % _px(sub)
    got = _f_lines(r) if irc == 0 else []
    assert irc == 0 and len(got) == 1 and got[0].casefold() == want.casefold(), (irc, got, want, out)


def test_i12_not_a_git_clone_zip_refused(box):
    zipdir = box.root / "zip" / "Fable"
    (zipdir / ".claude" / "hooks").mkdir(parents=True)
    r = _mk_repo(box, "z")
    irc, out = box.install(zipdir, r)
    assert irc != 0 and not (r / ".git" / "hooks" / "pre-commit").exists(), out


def test_i13_outside_any_repo_refused_nothing_written(box, fab):
    d = box.root / "norepo"
    d.mkdir()
    irc, out = box.install(fab, d, env={"GIT_CEILING_DIRECTORIES": str(box.root)})
    assert irc != 0 and not list(d.iterdir()), out


def test_i14_precommit_is_a_directory_refused(box, fab):
    r = _mk_repo(box, "dirhook")
    (r / ".git" / "hooks" / "pre-commit").mkdir()
    irc, out = box.install(fab, r)
    assert irc != 0 and not list((r / ".git" / "hooks" / "pre-commit").iterdir()), out


def test_i15_repo_without_hooks_dir_installs_and_red_guard_blocks(box, fab):
    r = box.root / "nohooks"
    box.git(box.root, "init", "-q", "--template=", str(r))
    (r / ".claude").mkdir()
    (r / ".claude" / "wiring-guards").write_bytes(b"false\n")
    irc, iout = box.install(fab, r)
    with open(r / "a", "ab") as fh:
        fh.write(b"a\n")
    box.git(r, "add", "a")
    rc, out = box.commit(r)
    assert (irc, rc) == (0, 1), (iout, out)


def test_i16_empty_hookspath_refused_nothing_written(box, fab):
    r = _mk_repo(box, "emptyhp")
    box.git(r, "config", "core.hooksPath", "")
    irc, out = box.install(fab, r)
    assert irc != 0 and not (r / "pre-commit").exists() \
        and not (r / ".git" / "hooks" / "pre-commit").exists(), out


def test_i17_symlink_precommit_refused_link_kept(box, fab):
    r = _mk_repo(box, "symhook")
    target = box.root / "linked_target"
    target.write_bytes(_thin_shell("x"))
    link = _px(r / ".git" / "hooks" / "pre-commit")
    box.sh("-c", 'ln -s "$1" "$2"', "ln", _px(target), link, cwd=r,
           env={"MSYS": "winsymlinks:nativestrict"})
    islink, _ = box.sh("-c", '[ -L "$1" ]', "t", link, cwd=r)
    if islink != 0:
        pytest.skip("本機無法建立原生 symlink（需要開發人員模式或系統管理員權限）")
    irc, out = box.install(fab, r)
    still, _ = box.sh("-c", '[ -L "$1" ]', "t", link, cwd=r)
    assert irc != 0 and still == 0, out


# ──────────────────────────── M：範本來源 ────────────────────────────

def _install_into_red_repo(box, fab):
    r = box.root / "p"
    box.git(box.root, "init", "-q", str(r))
    (r / ".claude").mkdir()
    (r / ".claude" / "wiring-guards").write_bytes(b"false\n")
    irc, out = box.install(fab, r)
    return r, irc, out


def test_m18_template_comes_from_main_not_working_tree(box, fab):
    shell = fab / ".claude" / "hooks" / "precommit_shell.sh"
    with open(shell, "ab") as fh:
        fh.write(b"# WIP-MARK\n")
    r, irc, out = _install_into_red_repo(box, fab)
    installed = (r / ".git" / "hooks" / "pre-commit").read_bytes()
    with open(r / "a", "ab") as fh:
        fh.write(b"a\n")
    box.git(r, "add", "a")
    rc, cout = box.commit(r)
    assert irc == 0 and b"WIP-MARK" not in installed and rc == 1, (irc, rc, out, cout)


def test_m19_fable_on_another_branch_still_installs_mains_template(box, fab):
    r, irc, out = _install_into_red_repo(box, fab)
    assert irc == 0, out
    shell = fab / ".claude" / "hooks" / "precommit_shell.sh"
    box.git(fab, "checkout", "-qb", "side")
    with open(shell, "ab") as fh:
        fh.write(b"# SIDE-MARK\n")
    box.git(fab, "commit", "-qam", "side")
    time.sleep(1.1)   # 備份檔名精度是秒；同一秒重裝會被正當拒絕，與本條無關
    irc2, out2 = box.install(fab, r)
    assert irc2 == 0, out2
    assert b"SIDE-MARK" not in (r / ".git" / "hooks" / "pre-commit").read_bytes()


# ──────────────────────────── 範本與腳本本身 ────────────────────────────

def test_x01_template_has_one_placeholder_and_lf_endings():
    data = SHELL_SRC.read_bytes()
    assert data.count(b"@FABLE@") == 1 and b"\r" not in data


def test_x02_installer_has_no_template_override():
    assert b"TPL" not in (REPO_ROOT / "scripts" / "install_precommit.sh").read_bytes()
