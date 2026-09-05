"""fable_doctor 健檢腳本的驗收測試——驗它抓得到「安裝看似成功、實際失效」的五種形態。

對應 reports/optimization_plan_20260826.md 的 N3（跨平台安裝器／doctor）與 N6（升級路徑斷裂）。
本檔為**公開可攜**測試：不含本機絕對路徑、不假設 ~/.claude 存在、不引用任何私有檔，
新使用者 clone 之後可直接重跑（對應 N4）。

驗收項目清單：
  D1 六個註冊齊備且直譯器可解析、副本與 repo 相同 → exit 0，problems 為空
  D2 settings.json 缺任一 hook → 該 hook 標 missing，exit 1
  D3 command 的直譯器路徑不存在 → 標 interpreter-unresolved，exit 1
     （這是 `|| exit 0` 會完全吃掉的那種失效——doctor 是唯一看得到它的地方）
  D4 已安裝的 skill／agents 副本與 repo 不同 → 標 copy-drift，exit 1（N6 的守衛）
  D5 install marker 的版本與 repo VERSION 不同 → 標 version-stale，exit 1（N6 的守衛）
  D6 hook 的 marker 檔從未出現 → 標 never-ran，exit 1
  D9 repo 裡每一支 Claude hook 腳本都出現在 doctor 的清單裡（通則，非個案斷言）
  D10 指令指向另一份 clone 的同名腳本 → 標 hook-elsewhere，exit 1
  D11 INSTALL.md 步驟 5 的六列與 doctor 清單逐項相同（文件與程式碼不得漂移）

執行命令：
  python -m pytest tests/test_fable_doctor.py -v

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-08-26 14:0x GMT+8）
══════════════════════════════════════
對應規劃：reports/optimization_plan_20260826.md §Z4 N3／§Z7 N6
執行命令：python -m pytest tests/test_fable_doctor.py -v
最後執行：2026-08-26 14:05 → 9 passed ✅

fail-then-pass 證據（實跑輸出，非轉述）：
  實作前：6 failed, 2 passed in 0.38s
          （D1~D6 全紅；D7 兩個 parametrize 案例先綠，因為 doctor 不存在時 argparse 也回非 0）
  實作後：9 passed in 1.24s
  ⚠ D7 首跑即綠＝該條當時無鑑別力，因此另補 D8 盯真實輸出字串（見下）。

D8 的來由（實跑真實安裝時發現的缺陷，非合成案例）：
  首版對 Stop hook 顯示 `last ran=never`，但 verify_gate.py 根本不寫 marker——
  那是把「沒有追蹤」報成「從未執行」。修正後真實輸出：
      SessionStart       interpreter=bash    last ran=2026-08-26 11:22:54
      UserPromptSubmit   interpreter=bash    last ran=2026-08-26 14:03:02
      Stop               interpreter=python  last ran=not tracked

對一份真實安裝實跑（`--home <使用者家目錄> --repo .`）：EXITCODE=1，
  唯一 problem＝install-marker-missing（本功能導入前未寫過該檔，屬預期）。

✅ 已驗收（本檔涵蓋）
  D1 健康安裝 → problems=[]、exit 0
  D2 缺 Stop hook → hook-missing、exit 1
  D3 直譯器路徑不存在 → interpreter-unresolved、exit 1
  D4 skill 副本內容不同 → copy-drift、exit 1
  D5 marker 版本 1.0.0 vs repo 9.9.9 → version-stale、exit 1
  D6 刪除 .last_sessionstart → never-ran、exit 1
  D7 缺 --home 或 --repo → returncode != 0
  D8 Stop/verify_gate.py 那行顯示 not tracked 且不含 never
  D9 .claude/hooks/ 下每支 .py／.sh（wiring_runner.sh 除外，它是 git hook）都在 doctor 清單裡

──────────────────────────────────────
2026-09-05 12:43 GMT+8 追加（組件 4／5 併入，v1.2.0）
──────────────────────────────────────
清單由「事件→腳本」改為 (事件, 腳本) 配對：goal_gate.py 掛在兩個事件上，
prompt_nudge.sh 與 goal_gate.py 同掛 UserPromptSubmit。以事件為鍵時，
同事件的第二支腳本會從清單裡消失——doctor 不會報錯，只是永遠不看它。

fail-then-pass（實跑輸出，非轉述）：
  改 doctor 之前：2 failed, 7 passed
    （D1 出現 3 個 hook-missing：兩個 goal_gate.py 註冊與 wiring_gate.py；D8 連帶 rc=1）
  修好 fixture（改 append，補六個註冊）之後：10 passed in 1.50s
  D9 突變：把 ("PreToolUse", "wiring_gate.py") 從 doctor 清單刪掉
    → 1 failed, 9 passed（訊息指名 'wiring_gate.py'）；還原 → 10 passed in 1.44s

2026-09-05 13:09 追加 D10／D11（抗辯發現）：
  D10 的來由是**真實安裝當下就處於該狀態**：全域 settings 把三支新 hook 註冊在
  另一份 clone，而 doctor 只比對檔名，於是六列全部顯示正常。
  修好後對真實安裝實跑，三列被標 hook-elsewhere（見收工回報）。
  突變：把路徑比對關掉 → D10 翻紅；刪掉 INSTALL 表格一列 → D11 翻紅；
  各自只翻自己那一條，還原 → 12 passed。
最後執行：2026-09-05 14:59 → 12 passed ✅

⏳ 待驗收（本檔未涵蓋）
  真實 ~/.claude 的端到端安裝：需乾淨機器，屬 N5 測試矩陣，不在單元測試範圍。
  三平台差異（macOS/Linux 的 python3、Windows 的 WSL bash 誤判）：本檔以合成路徑模擬，
    真實直譯器解析行為需在該平台實跑，解鎖條件＝取得對應平台的乾淨環境。
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCTOR = REPO_ROOT / "scripts" / "fable_doctor.py"

# 三個 skill 都是「複製」交付，都會隨版本漂移——doctor 必須逐個比對
SKILL_DIRS = ("adversarial-review", "cognitive-rubrics", "model-dispatch-rules")

# (event, script)：一個事件可掛多支腳本，而 goal_gate.py 掛在兩個事件上。
# 用 dict 以事件為鍵會讓同事件的第二支腳本從清單裡消失——doctor 也一樣，故兩邊同構。
HOOK_SCRIPTS = [
    ("SessionStart", "inject_protocol.sh"),
    ("UserPromptSubmit", "prompt_nudge.sh"),
    ("UserPromptSubmit", "goal_gate.py"),
    ("Stop", "verify_gate.py"),
    ("Stop", "goal_gate.py"),
    ("PreToolUse", "wiring_gate.py"),
]


def _make_repo(tmp_path: Path, version: str = "9.9.9") -> Path:
    """建一個最小的假 repo：五支 hook 腳本、skill、agents、VERSION。"""
    repo = tmp_path / "repo"
    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    for name in {script for _, script in HOOK_SCRIPTS}:
        (hooks / name).write_text("# stub\n", encoding="utf-8")
    for skill_name in SKILL_DIRS:
        skill = repo / ".claude" / "skills" / skill_name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"{skill_name} body\n", encoding="utf-8")
    agents = repo / ".claude" / "agents"
    agents.mkdir(parents=True)
    for a in ("skeptic", "red-team", "simplifier"):
        (agents / f"{a}.md").write_text(f"{a} body\n", encoding="utf-8")
    (repo / "VERSION").write_text(version + "\n", encoding="utf-8")
    return repo


def _make_home(tmp_path: Path, repo: Path, version: str = "9.9.9") -> Path:
    """建一個「安裝正確」的假 ~/.claude：settings 六個註冊、副本一致、marker 已寫、版本相符。"""
    home = tmp_path / "home"
    claude = home / ".claude"
    claude.mkdir(parents=True)

    interp = sys.executable  # 保證存在的直譯器，讓 D1 不會誤判
    hooks_dir = repo / ".claude" / "hooks"
    settings = {"hooks": {}}
    for event, script in HOOK_SCRIPTS:
        cmd = f'"{interp}" "{(hooks_dir / script).as_posix()}" || exit 0'
        # append：同一事件掛第二支腳本時覆寫會讓第一支消失，而 doctor 只會說「沒註冊」，
        # 看起來像 doctor 壞了，實際上是這個 fixture 壞了。
        settings["hooks"].setdefault(event, []).append(
            {"matcher": "*", "hooks": [{"type": "command", "command": cmd}]}
        )
    (claude / "settings.json").write_text(
        json.dumps(settings, indent=2), encoding="utf-8"
    )

    for skill_name in SKILL_DIRS:
        dst_skill = claude / "skills" / skill_name
        dst_skill.mkdir(parents=True)
        (dst_skill / "SKILL.md").write_text(f"{skill_name} body\n", encoding="utf-8")
    dst_agents = claude / "agents"
    dst_agents.mkdir(parents=True)
    for a in ("skeptic", "red-team", "simplifier"):
        (dst_agents / f"{a}.md").write_text(f"{a} body\n", encoding="utf-8")

    (claude / "fable-harness-install.json").write_text(
        json.dumps({"repo_path": str(repo), "version": version}), encoding="utf-8"
    )

    # hook 觸發 marker（表示真的跑過）
    for marker in (".last_sessionstart", ".last_promptsubmit"):
        (repo / ".claude" / "hooks" / marker).write_text("2026-08-26 00:00:00\n", encoding="utf-8")
    return home


def _run(home: Path, repo: Path):
    proc = subprocess.run(
        [sys.executable, str(DOCTOR), "--home", str(home), "--repo", str(repo), "--json"],
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload


def _codes(payload) -> set:
    return {p["code"] for p in payload.get("problems", [])}


def test_d1_healthy_install_reports_no_problems(tmp_path):
    """D1：一個完全正確的安裝 → exit 0，problems 空。"""
    repo = _make_repo(tmp_path)
    home = _make_home(tmp_path, repo)
    rc, payload = _run(home, repo)
    assert payload.get("problems") == [], f"健康安裝不該有 problem：{payload.get('problems')}"
    assert rc == 0, f"健康安裝應 exit 0，實得 {rc}"


def test_d2_missing_hook_is_reported(tmp_path):
    """D2：settings 缺 Stop hook → 標 missing 並 exit 1。"""
    repo = _make_repo(tmp_path)
    home = _make_home(tmp_path, repo)
    settings_path = home / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    del data["hooks"]["Stop"]
    settings_path.write_text(json.dumps(data), encoding="utf-8")

    rc, payload = _run(home, repo)
    assert "hook-missing" in _codes(payload), f"缺 hook 未被回報：{payload}"
    assert rc == 1


def test_d3_unresolved_interpreter_is_reported(tmp_path):
    """D3：直譯器路徑不存在 → 標 interpreter-unresolved 並 exit 1。

    這正是 `|| exit 0` 會完全吞掉的失效——沒有 doctor 就看不見。
    """
    repo = _make_repo(tmp_path)
    home = _make_home(tmp_path, repo)
    settings_path = home / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    bogus = (tmp_path / "no_such_interpreter_xyz").as_posix()
    entry = data["hooks"]["SessionStart"][0]["hooks"][0]
    entry["command"] = f'"{bogus}" "{(repo / ".claude/hooks/inject_protocol.sh").as_posix()}" || exit 0'
    settings_path.write_text(json.dumps(data), encoding="utf-8")

    rc, payload = _run(home, repo)
    assert "interpreter-unresolved" in _codes(payload), f"不存在的直譯器未被回報：{payload}"
    assert rc == 1


def test_d4_copy_drift_is_reported(tmp_path):
    """D4：已安裝的 skill 副本與 repo 不同 → 標 copy-drift 並 exit 1（N6 守衛）。"""
    repo = _make_repo(tmp_path)
    home = _make_home(tmp_path, repo)
    (home / ".claude" / "skills" / "cognitive-rubrics" / "SKILL.md").write_text(
        "OLD cognitive-rubrics body\n", encoding="utf-8"
    )

    rc, payload = _run(home, repo)
    assert "copy-drift" in _codes(payload), f"副本漂移未被回報：{payload}"
    assert rc == 1


def test_d5_stale_version_marker_is_reported(tmp_path):
    """D5：install marker 版本落後 repo VERSION → 標 version-stale 並 exit 1（N6 守衛）。"""
    repo = _make_repo(tmp_path, version="9.9.9")
    home = _make_home(tmp_path, repo, version="1.0.0")

    rc, payload = _run(home, repo)
    assert "version-stale" in _codes(payload), f"版本落後未被回報：{payload}"
    assert rc == 1


def test_d6_hook_never_ran_is_reported(tmp_path):
    """D6：hook 的觸發 marker 從未出現 → 標 never-ran 並 exit 1。"""
    repo = _make_repo(tmp_path)
    home = _make_home(tmp_path, repo)
    (repo / ".claude" / "hooks" / ".last_sessionstart").unlink()

    rc, payload = _run(home, repo)
    assert "never-ran" in _codes(payload), f"從未執行的 hook 未被回報：{payload}"
    assert rc == 1


def test_d8_untracked_hook_is_not_reported_as_never_ran(tmp_path):
    """D8：Stop hook 不寫 marker → 不得被判 never-ran，人類輸出也不得寫「never」。

    「我們沒有追蹤這個」與「它從來沒跑過」是兩件事。把前者顯示成後者，
    正是這支工具存在的理由（fail-open 被讀成已驗證）的同型錯誤。
    """
    repo = _make_repo(tmp_path)
    home = _make_home(tmp_path, repo)
    rc, payload = _run(home, repo)
    assert rc == 0 and payload["problems"] == []

    proc = subprocess.run(
        [sys.executable, str(DOCTOR), "--home", str(home), "--repo", str(repo)],
        capture_output=True,
        text=True,
    )
    stop_line = [ln for ln in proc.stdout.splitlines() if "Stop/verify_gate.py" in ln]
    assert stop_line, f"人類輸出沒有 Stop/verify_gate.py 那一行：{proc.stdout}"
    assert "not tracked" in stop_line[0], f"Stop 應顯示 not tracked，實得：{stop_line[0]}"
    assert "never" not in stop_line[0], f"Stop 不得顯示 never：{stop_line[0]}"


def test_d10_hook_registered_from_another_clone_is_reported(tmp_path):
    """D10：指令指向**另一份 clone** 的同名腳本 → 必須報 hook-elsewhere。

    只比對檔名時，這種情況顯示為「已註冊、直譯器正常」，而實際執行的是別處的
    程式碼——doctor 報的版本與副本屬於這個 repo，跑的卻不是。這正是本工具
    要消滅的那種靜默錯裝，2026-09-05 在真實安裝上就是這個狀態。
    """
    repo = _make_repo(tmp_path)
    other = tmp_path / "other_clone" / ".claude" / "hooks"
    other.mkdir(parents=True)
    (other / "verify_gate.py").write_text("# stub\n", encoding="utf-8")
    home = _make_home(tmp_path, repo)
    settings_path = home / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    for group in data["hooks"]["Stop"]:
        entry = group["hooks"][0]
        if "verify_gate.py" in entry["command"]:
            entry["command"] = (
                f'"{sys.executable}" "{(other / "verify_gate.py").as_posix()}" || exit 0'
            )
    settings_path.write_text(json.dumps(data), encoding="utf-8")

    rc, payload = _run(home, repo)
    assert "hook-elsewhere" in _codes(payload), f"指向別的 clone 未被回報：{payload}"
    assert rc == 1


def test_d9_every_hook_script_in_the_repo_is_watched():
    """D9：repo 裡每一支 Claude hook 腳本都必須出現在 doctor 的清單裡。

    通則而非個案：寫成「wiring_gate 要在清單裡」只擋得住這一次；
    下一個組件加進來時，這條才會紅。少了它，新 hook 對健檢隱形——
    而健檢正是「安裝看似成功、實際失效」的唯一可見處。

    wiring_runner.sh 不在此列：它是安裝到 repo 的 .git/hooks/pre-commit 的
    git hook，不是註冊在 settings.json 裡的 Claude hook，doctor 管不到它。
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import fable_doctor  # noqa: PLC0415

    watched = {script for _, script in fable_doctor.HOOK_SCRIPTS}
    hooks_dir = REPO_ROOT / ".claude" / "hooks"
    not_claude_hooks = {"wiring_runner.sh"}
    on_disk = {
        p.name for p in hooks_dir.iterdir()
        if p.is_file() and p.suffix in (".py", ".sh") and p.name not in not_claude_hooks
    }
    assert on_disk <= watched, f"這些 hook 沒被 doctor 盯著：{sorted(on_disk - watched)}"


def test_d11_install_table_and_doctor_list_cannot_drift():
    """D11：INSTALL.md 步驟 5 的註冊表，必須與 doctor 的清單逐項相同。

    兩邊都是「這個 kit 有哪些 hook」的敘述，而它們分屬文件與程式碼——
    加一個組件時只改一邊不會有任何徵兆：安裝的人照文件裝，健檢照清單看，
    少的那一個兩邊都不會叫。這條測試把「同步」變成會紅的事。
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import fable_doctor  # noqa: PLC0415

    install = (REPO_ROOT / "INSTALL.md").read_text(encoding="utf-8")
    row = re.compile(
        r"^\s*\|\s*`(\w+)`\s*\|\s*`<repo>/\.claude/hooks/([\w.]+)[^`]*`", re.M)
    documented = {(m.group(1), m.group(2)) for m in row.finditer(install)}
    assert documented, "INSTALL.md 步驟 5 的表格解析不到任何一列——格式改了就要更新這條"
    assert documented == set(fable_doctor.HOOK_SCRIPTS), (
        f"INSTALL.md 與 doctor 清單不一致：\n"
        f"  只在文件：{sorted(documented - set(fable_doctor.HOOK_SCRIPTS))}\n"
        f"  只在程式：{sorted(set(fable_doctor.HOOK_SCRIPTS) - documented)}"
    )


@pytest.mark.parametrize("flag", ["--home", "--repo"])
def test_d7_missing_required_flag_fails_loudly(tmp_path, flag):
    """D7 配對測試：doctor 缺必要參數時要明確報錯，不得靜默通過。

    與 D1~D6「必須被抓到」配對——一個「什麼都回報 OK」的 doctor 也會讓 D1 通過，
    這條確保它在輸入不足時不會假裝健康。
    """
    repo = _make_repo(tmp_path)
    home = _make_home(tmp_path, repo)
    args = [sys.executable, str(DOCTOR), "--json"]
    if flag == "--home":
        args += ["--repo", str(repo)]
    else:
        args += ["--home", str(home)]
    proc = subprocess.run(args, capture_output=True, text=True)
    assert proc.returncode != 0, "缺必要參數卻回 0——doctor 在裝健康"
