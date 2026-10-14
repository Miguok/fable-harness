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
  I01 取代本 kit 舊複本（runner 複本／舊薄殼），守衛只跑一次、舊檔備份
  I02 連裝兩次不覆蓋第一份備份，備份檔名 .bak.YYYYMMDD-HHMMSS
  I10 路徑含 " $ ` 拒絕且不寫任何檔；I03 非本 kit 的 hook 拒絕且不動；I04 使用者 hook 內嵌
  舊 runner 也拒絕；I05/I06/I16 core.hooksPath（相對／絕對／空字串）拒絕；I08 備份失敗不取代
  I09 訊息點名備份路徑；I07 路徑（含 & 與反斜線）原樣寫入 F=；I11 相對路徑存成絕對路徑
  I12 非 git clone（ZIP）拒絕；I13 repo 外執行拒絕；I14 pre-commit 是目錄拒絕
  I15 沒有 hooks 目錄的 repo 可裝且紅守衛擋得住；I17 pre-commit 是 symlink 拒絕
  M18 範本取自 Fable main，不取工作樹未 commit 的改動；M19 Fable 在別的分支，仍取 main
  X01 範本只有一個 @FABLE@ 且是 LF；X02 安裝腳本沒有範本覆寫分支

執行命令（repo 根目錄）：
  python -m pytest tests/test_precommit_shell.py -q -p no:cacheprovider

測試自建「假 Fable」repo（git init -b main，只放本 worktree 的 runner 與薄殼），
不 clone、不讀寫任何真實 Fable／Finzo 目錄。

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-10-14 23:04 GMT+8）
══════════════════════════════════════
對應規劃書：INSTALL.md 步驟 10；CHANGELOG [Unreleased] 的 pre-commit 薄殼條目
執行命令：python -m pytest tests/test_precommit_shell.py -q -p no:cacheprovider
最後執行：2026-10-14 23:04 → 42 passed ✅

[關鍵量測]
  TDD 紅燈（薄殼與安裝腳本尚未建立）：2 failed, 1 passed, 39 errors（fixture 讀不到 precommit_shell.sh）
  綠燈：42 passed（R17 + I21 + M2 + X2；I01/I07 各參數化 2 格、I10 參數化 3 格）；原生 symlink 可建，I17 未 skip
  突變（舊讀法 `git -C "$F" ... main:<path>` 的薄殼）：9 failed, 33 passed
    翻紅：R04 R05 R06 R08 R14 R15 R16 I01[2] M19——即 linked worktree／--git-dir／同名 tag 等
    git 匯出環境與歧義情境；舊讀法在這些情境讀到被保護 repo 或錯誤的 ref
  全套 tests/：498 passed, 3 skipped（基準 456 passed, 3 skipped，+42）

✅ 已驗收（本檔涵蓋）
  R01-R17 → 紅 rc=1／綠 rc=0／ALLOW_UNWIRED rc=0，且 DECOY-RAN 從未出現在輸出
  I01-I17 → 拒絕案例 rc≠0 且 hook 內容或目錄零變動；允許案例 F= 行與預期路徑逐字相等（忽略大小寫）
  M18/M19 → 範本取自 main：工作樹的 WIP-MARK、另一分支的 SIDE-MARK 都不會被裝進 hook
⏳ 待驗收（本檔未涵蓋）
  真實 Fable／真實已裝 repo 的升級路徑：本檔刻意只用假 Fable，不碰真實目錄；
    解鎖條件＝本分支合併進 Fable main 並經使用者點頭後，在一個拋棄式 repo 上實跑安裝腳本一次
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

    def attempt(self, cwd, guard, env=None):
        """寫入宣告、改一個檔、commit；回 (rc, 輸出)。"""
        cwd = Path(cwd)
        (cwd / ".claude").mkdir(exist_ok=True)
        (cwd / ".claude" / "wiring-guards").write_bytes((guard + "\n").encode())
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
