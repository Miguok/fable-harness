# -*- coding: utf-8 -*-
"""goal_gate（組件 5）的驗收——第三階：接了線、跑了測試，目標還是沒達成。

驗收項目清單：
  G1  沒跑測試的一輪 → 不計數、不介入
  G2  測試全綠 → 不介入，且把既有連敗數歸零
  G3  連敗第 1 次 → 不介入（找根因、修、重測是正常工作）
  G4  連敗第 2 次 → 擋一次，要求下一次動手前先跑抗辯
  G5  連敗第 3 次 → 擋一次、自動寫入擱置清單、連敗數歸零
  G6  `stop_hook_active` → 一律放行（第二次結束必過，永不死鎖）
  G7  擱置項的 note 還空著 → 擋一次要求寫下擱置原因
  G8  note 填好之後 → 不再擋（一次性動作，不變成嘮叨）
  G9  這一輪文字提到擱置項 id → **仍要擋**（只有填 note 才解除；見下方修復記錄）
  G14 state 檔壞掉／讀不到 → 不得覆寫（使用者手寫的 note 會被清空）
  G15 `no tests ran` 這種空綠 → 不得歸零連敗數
  G16 失敗指令的 env 前綴（`TOKEN=… pytest`）存檔與回吐前必須遮蔽
  G10 UserPromptSubmit → 把擱置清單注入（用戶回來就看得到）
  G11 UserPromptSubmit 而清單為空 → 靜默
  G12 門檻可由 env 調整（FABLE_GOAL_ADVERSARIAL_AT / _SHELVE_AT）
  G13 輸入壞掉 / 不在 git repo → fail-open，無輸出、exit 0

執行命令：
  cd <repo> && python -m pytest tests/test_goal_gate.py -v

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-09-05 12:55 GMT+8）
══════════════════════════════════════
對應：CHANGELOG 1.2.0「新增組件 5 goal gate」。

門檻的來源與既有規則的關係（動筆前實查，非印象）：
  cognitive_rubrics.md:35 「同一方法連續失敗 2 次 → 換路，不是第 3 次重試」→ 管【方法】
  cognitive_rubrics.md:13 「同一錯誤第二次出現」→ 管【錯誤復發】
  model_dispatch_rules.md:52 「子代理交出實質錯誤 1 次即升級」→ 管【子代理結果】
  本檔 → 管【目標未達成】，是第四個計數器。
  cognitive_rubrics.md 第 13/35/45 行三度明令這些計數器**不得合併**，
  所以本檔另立狀態、另立門檻，不去動既有那三條。

G5 的設計要點：擱置項由 gate **自己寫入**，不是叫 agent 記得去寫。
理由與整個階梯一致——「靠人記得」正是這三階要消滅的東西。

G7/G8 的設計要點：擋的條件是「note 還空著」，不是「這一輪沒提到它」。
後者會在每一個不相關的回合都觸發，而嘮叨的閘門會被繞過；
前者是一次性動作，做完就永久解除，因此可執行。

──────────────────────────────────────
2026-09-05 13:09 GMT+8：抗辯抓出的四個缺陷修復（G9 語意反轉、G14～G16）
──────────────────────────────────────
G9 原本斷言「提到 id 就放行」——那與上一段寫的設計要點**互相矛盾**，
而程式碼實作的是 G9 那一版：於是 §4b「用戶回來時先把擱置項講出來」
變成這道閘的解鎖碼，note 永遠不會被寫。本輪把程式改成只認 note，
G9 的期望隨之反轉（提 id 仍要擋）。文件與程式不一致時，先問哪一個
是設計、哪一個是缺陷，不要選比較好改的那一個。

四個突變（每個只翻自己那一條，還原後 29 passed）：
  M-1 load_state 讀不到就回空狀態      → G14 翻紅
  M-2 拿掉空綠過濾（vacuous 當成 pass）→ G15 翻紅
  M-3 恢復「提到 id 就放行」            → G9 翻紅
  M-4 拿掉 redact                       → G16 翻紅
最後執行：2026-09-05 14:59（三輪抗辯修復後）→ 39 passed ✅

併入本 repo 當時（12:52，26 passed）的抽樣突變：
  把 _looks_failed 改回「整段輸出裡有沒有出現過失敗」（1.2.2 的根因形態）
    → 3 failed, 23 passed（兩條軟性標記案 + 單一呼叫內的紅→綠循環案翻紅）
    → 還原 → 26 passed

✅ 已驗收（本檔涵蓋）
  G1-G13，皆驅動真實的 .claude/hooks/goal_gate.py 與真實的 JSONL transcript
⏳ 待驗收（本檔未涵蓋）
  Claude Code 真的把 decision:block 當成擋下收工：與 verify_gate 用的是同一個
  block 封包格式（該機制已由 verify_gate 在真實 session 驗證過），但本 gate 的
  兩種 block 尚未在真實 session 觸發過。解鎖條件＝連續兩次紅燈後觀察它是否擋下收工。
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(ROOT, ".claude", "hooks", "goal_gate.py")
STATE_REL = os.path.join(".fable", "goal_state.json")

PASS_OUT = "collected 12 items\n............\n12 passed in 1.20s\n"
FAIL_OUT = ("collected 12 items\n...F........\n"
            "FAILED tests/test_x.py::test_y - AssertionError: nope\n"
            "1 failed, 11 passed in 1.31s\n")


def _turn(cmd=None, output=None, assistant_text=None, uid="tu1"):
    """One user prompt followed by an optional test run and its result."""
    entries = [{"type": "user", "message": {"content": "do the thing"}}]
    if cmd is not None:
        entries.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": uid, "name": "Bash",
             "input": {"command": cmd}}]}})
        entries.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": uid,
             "content": [{"type": "text", "text": output or ""}]}]}})
    if assistant_text:
        entries.append({"type": "assistant", "message": {"content": [
            {"type": "text", "text": assistant_text}]}})
    return entries


def _repo(tmp_path, state=None):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    if state is not None:
        d = tmp_path / ".fable"
        d.mkdir(exist_ok=True)
        (d / "goal_state.json").write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8", newline="")
    return tmp_path


def _run(repo, entries=None, payload=None, env=None):
    tp = repo / "transcript.jsonl"
    if entries is not None:
        tp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n"
                              for e in entries), encoding="utf-8", newline="")
    data = payload if payload is not None else {"transcript_path": str(tp)}
    e = dict(os.environ)
    e.update(env or {})
    out = subprocess.run([sys.executable, GATE], input=json.dumps(data),
                         capture_output=True, encoding="utf-8", errors="replace",
                         cwd=str(repo), env=e, timeout=60)
    assert out.returncode == 0, f"gate 不得非零退出（fail-open 契約）: {out.stderr}"
    return out.stdout.strip()


def _blocked(stdout):
    return bool(stdout) and json.loads(stdout).get("decision") == "block"


def _reason(stdout):
    return json.loads(stdout)["reason"]


def _state(repo):
    return json.loads((repo / STATE_REL).read_text(encoding="utf-8"))


# ── 計數 ──────────────────────────────────────────────────────────────────
def test_g1_no_test_in_the_turn_is_not_counted(tmp_path):
    repo = _repo(tmp_path)
    assert _run(repo, _turn(cmd="ls -la", output="x")) == ""
    assert not (repo / STATE_REL).exists()


def test_g2_green_run_resets_the_streak(tmp_path):
    repo = _repo(tmp_path, {"streak": 2, "shelved": []})
    assert _run(repo, _turn("pytest -q", PASS_OUT)) == ""
    assert _state(repo)["streak"] == 0


@pytest.mark.parametrize("output,expect_counted", [
    # 全綠，但輸出裡有「AssertionError」字樣——測試在斷言某段會拋例外時很常見。
    ("12 passed in 1.2s\ncaptured log: AssertionError: expected\n", False),
    # 全綠，但某個 docstring 印出了 FAILED 開頭的行
    ("FAILED is the word we print in the help text\n8 passed in 0.3s\n", False),
    # 真的失敗：計數型摘要單獨即可斷定
    ("2 failed, 10 passed in 1.2s\n", True),
    # 真的失敗：只有 error 計數
    ("3 errors in 0.5s\n", True),
])
def test_g3_soft_markers_in_a_passing_run_are_not_failures(tmp_path, output, expect_counted):
    """誤判成失敗會讓 gate 在正常工作上嘮叨，而嘮叨的閘門會被繞過。"""
    repo = _repo(tmp_path)
    _run(repo, _turn("pytest -q", output))
    streak = _state(repo)["streak"] if (repo / STATE_REL).exists() else 0
    assert streak == (1 if expect_counted else 0)


def _multi_turn(runs):
    """One user prompt then a sequence of (command, output) test runs."""
    entries = [{"type": "user", "message": {"content": "do the thing"}}]
    for i, (cmd, out) in enumerate(runs):
        uid = f"t{i}"
        entries.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": uid, "name": "Bash",
             "input": {"command": cmd}}]}})
        entries.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": uid,
             "content": [{"type": "text", "text": out}]}]}})
    return entries


def test_g3_mutation_testing_is_not_a_failed_attempt(tmp_path):
    """突變測試是本協議**要求**的做法，形態必然是紅→紅→紅→綠。

    2026-09-05 實例：本 gate 上線不到一小時就對它作者的突變測試開火。
    量錯了對象——該量的是「這次嘗試最後是不是還在失敗」，
    不是「這一輪有沒有出現過失敗」。fail-then-pass 證據同理。
    """
    repo = _repo(tmp_path)
    cmd = "pytest -q collect/test/test_guard.py"
    _run(repo, _multi_turn([
        (cmd, FAIL_OUT),   # 突變 1：拿掉守門 → 預期紅
        (cmd, FAIL_OUT),   # 突變 2
        (cmd, FAIL_OUT),   # 突變 3
        (cmd, PASS_OUT),   # 還原 → 綠
    ]))
    streak = _state(repo)["streak"] if (repo / STATE_REL).exists() else 0
    assert streak == 0, "紅→綠的突變循環不得被算成失敗的嘗試"


CONCATENATED_MUTATION_RUN = (
    "10 passed in 0.56s\n"
    "=== 突變：把守門拿掉 ===\n"
    "突變已落地\n"
    "FAILED tests/test_guard.py::test_d9 - AssertionError\n"
    "1 failed, 9 passed in 1.13s\n"
    "=== 還原 ===\n"
    "10 passed in 0.78s\n"
)


def test_g3_one_shell_call_containing_a_whole_red_green_cycle(tmp_path):
    """一個 Bash 呼叫裡跑完整個突變循環——只有一個 tool_result，輸出三段串接。

    2026-09-05 的第二次誤報就是這個形態：v1.2.1 以「指令字串」為鍵去重覆，
    而整段多行腳本是**一個鍵、一個結果**，切不開。判準因此改成
    「輸出裡最後一行測試摘要說什麼」——這裡是 10 passed。
    """
    repo = _repo(tmp_path)
    _run(repo, _turn("pytest -q tests/test_guard.py && mutate && pytest -q",
                     CONCATENATED_MUTATION_RUN))
    streak = _state(repo)["streak"] if (repo / STATE_REL).exists() else 0
    assert streak == 0, "同一呼叫內的紅→綠循環不得被算成失敗的嘗試"


def test_g3_concatenated_run_that_ends_red_is_still_a_failure(tmp_path):
    """與上一條配對：末段仍紅就必須計數，否則等於把 gate 關掉。"""
    repo = _repo(tmp_path)
    ends_red = CONCATENATED_MUTATION_RUN.replace(
        "10 passed in 0.78s", "2 failed, 8 passed in 0.81s")
    _run(repo, _turn("pytest -q && mutate && pytest -q", ends_red))
    assert _state(repo)["streak"] == 1


SCRIPT_STYLE_CRASH = (
    "Traceback (most recent call last):\n"
    '  File "test_probe.py", line 42, in main\n'
    "    assert rows == expected\n"
    "AssertionError\n"
)


def test_g3_output_with_no_summary_line_falls_back_to_soft_markers(tmp_path):
    """沒有摘要行的失敗仍要被算到。

    script 式測試（`main()` 模式、`python test_x.py`）拋例外時只有 traceback，
    不會印 `N passed / N failed`。少了這條 fallback，那類失敗會被判成沒事——
    而它是這個 repo 明文允許的測試形態。
    """
    repo = _repo(tmp_path)
    _run(repo, _turn("python test_probe.py --test", SCRIPT_STYLE_CRASH))
    assert _state(repo)["streak"] == 1


def test_g3_script_style_success_is_not_a_failure(tmp_path):
    """與上一條配對：同樣沒有摘要行，但沒有失敗跡象 → 不得計數。"""
    repo = _repo(tmp_path)
    _run(repo, _turn("python test_probe.py --test", "OK: 12 checks\ndone\n"))
    streak = _state(repo)["streak"] if (repo / STATE_REL).exists() else 0
    assert streak == 0


def test_g21_same_target_through_a_different_pipe_is_one_target(tmp_path):
    """G21：`… | tail -14` 與 `… | tail -2` 是同一次測試，不是兩個目標。

    以整條指令字串當鍵時，修好後換個輸出裁切重跑，綠燈就落在**另一個鍵**上，
    紅的那個永遠留著——連敗數只增不減。2026-09-05 實測兩次擋到這道閘自己的
    作者，兩次都是「已經修好、只是 tail 的數字不同」。
    """
    repo = _repo(tmp_path)
    _run(repo, _multi_turn([
        ("python x_test.py 2>&1 | tail -14", FAIL_OUT),
        ("python x_test.py 2>&1 | tail -2", PASS_OUT),
    ]))
    streak = _state(repo)["streak"] if (repo / STATE_REL).exists() else 0
    assert streak == 0, "同一個目標修好了，連敗數卻沒歸零"


def test_g22_same_target_wrapped_in_shell_plumbing_is_one_target(tmp_path):
    """G22：`cd x && sed -i … && pytest t.py` 與單獨的 `pytest t.py` 是同一個目標。

    G21 只切掉了管線尾巴，前綴仍然進鍵——於是「改完順手重跑」與「單獨重跑」
    落在兩個鍵上，紅的那個永遠留著。2026-09-05 第三次擋到這道閘自己的作者，
    就是這個形態。
    """
    repo = _repo(tmp_path)
    _run(repo, _multi_turn([
        ('cd d:/x && sed -i "s/a/b/" t.py && python -m pytest tests/t.py -q', FAIL_OUT),
        ('python -m pytest tests/t.py -q 2>&1 | tail -4', PASS_OUT),
    ]))
    streak = _state(repo)["streak"] if (repo / STATE_REL).exists() else 0
    assert streak == 0, "同一個目標修好了，連敗數卻沒歸零"


@pytest.mark.parametrize("cmd", [
    "python -m pytest tests/t.py --collect-only -q",
    "pytest --version",
    "pytest --fixtures",
])
def test_g23_listing_is_not_running(tmp_path, cmd):
    """G23：`--collect-only`／`--version` 這類指令沒有執行任何測試。

    把它們的輸出當成目標的成敗，等於把「我在數東西」讀成「我的修法失敗了」。
    2026-09-05 實測：用 `--collect-only` 去數某個 tag 上的案例數（輸出含
    `1 error`），被算成連敗一次，接著就擋下收工。
    """
    repo = _repo(tmp_path)
    assert _run(repo, _turn(cmd, "no tests collected, 1 error in 0.63s")) == ""
    streak = _state(repo)["streak"] if (repo / STATE_REL).exists() else 0
    assert streak == 0, "只是列出測試，卻被算成一次失敗的執行"


def test_g3_a_later_green_on_another_target_does_not_mask_a_red_one(tmp_path):
    """每個測試指令各看自己最後一次——否則事後跑一支必綠的測試就能蓋掉真失敗。"""
    repo = _repo(tmp_path)
    _run(repo, _multi_turn([
        ("pytest -q tests/test_real.py", FAIL_OUT),   # 真的還紅著
        ("pytest -q tests/test_trivial.py", PASS_OUT),  # 另一支綠的
    ]))
    assert _state(repo)["streak"] == 1


def test_g3_first_failure_does_not_interfere(tmp_path):
    repo = _repo(tmp_path)
    assert _run(repo, _turn("pytest -q", FAIL_OUT)) == ""
    assert _state(repo)["streak"] == 1


def test_g4_second_failure_demands_adversarial_review(tmp_path):
    repo = _repo(tmp_path, {"streak": 1, "shelved": []})
    out = _run(repo, _turn("pytest -q", FAIL_OUT))
    assert _blocked(out)
    assert "adversarial review" in _reason(out)
    assert _state(repo)["streak"] == 2


def test_g5_third_failure_shelves_the_item(tmp_path):
    repo = _repo(tmp_path, {"streak": 2, "shelved": []})
    out = _run(repo, _turn("pytest -q tests/test_x.py", FAIL_OUT))
    assert _blocked(out)
    assert "shelving it" in _reason(out)
    st = _state(repo)
    assert st["streak"] == 0, "擱置後計數必須歸零，否則下一個目標一開始就在第 3 格"
    assert len(st["shelved"]) == 1
    item = st["shelved"][0]
    assert item["streak"] == 3
    assert "tests/test_x.py" in item["last_command"], "擱置項必須帶著當時的失敗指令"
    assert item["note"] == "", "note 由 agent 事後補寫，gate 只負責建立條目"


@pytest.mark.parametrize("cmd,gone,kept", [
    # 遮該遮的：空白分隔的機密旗標也算。
    ("pytest -q --token ghp_secret123", "ghp_secret123", "pytest"),
    # 不遮不該遮的：擱置項的用途就是讓人認出當時卡在哪。
    ("make test FILE=tests/test_auth.py CASE=login", None, "FILE=tests/test_auth.py"),
    ("pytest -q --maxfail=2", None, "--maxfail=2"),
])
def test_g18_masking_is_narrow_enough_to_stay_useful(tmp_path, cmd, gone, kept):
    """G18：遮蔽的對象是**看起來像機密的鍵**，不是每一個等號。

    全遮會把 `FILE=tests/test_auth.py CASE=login` 變成 `FILE=*** CASE=***`——
    記錄還在，但已經看不出卡在哪，等於把這條擱置項變成廢話。
    """
    repo = _repo(tmp_path, {"streak": 2, "shelved": []})
    _run(repo, _turn(cmd, FAIL_OUT))
    stored = _state(repo)["shelved"][0]["last_command"]
    if gone:
        assert gone not in stored, f"機密沒遮到：{stored}"
    assert kept in stored, f"遮過頭，認不出測試目標了：{stored}"


def test_g19_a_test_tool_that_never_ran_is_vacuous(tmp_path):
    """G19：測試工具根本沒跑起來，也是「沒跑到測試」，不得當成通過。

    與 G15 同類：那條只認得 pytest 自報的 `no tests ran`，
    而 `No module named pytest` 一樣是「這次沒有任何測試被執行」。
    """
    repo = _repo(tmp_path, {"streak": 1, "shelved": []})
    assert _run(repo, _turn("pytest -q", "No module named pytest\n")) == ""
    assert _state(repo)["streak"] == 1, "工具沒跑起來卻把連敗數清掉了"


def test_g20_hand_edited_shelf_missing_keys_still_surfaces(tmp_path):
    """G20：手改過的擱置項少了欄位，清單仍要浮出來。

    擋人的訊息本身就叫使用者去手改那份 JSON 填 note。若手改後缺一個欄位就
    KeyError、被 fail-open 吞掉，整份擱置清單會從此不再出現——
    這道閘自己的指示把自己關掉。
    """
    repo = _repo(tmp_path, {"streak": 0, "shelved": [{"id": "goal-9", "note": "手寫說明"}]})
    out = _run(repo, payload={"hook_event_name": "UserPromptSubmit"})
    assert "goal-9" in out and "手寫說明" in out


def test_g17_state_dir_ignores_itself(tmp_path):
    """G17：狀態目錄要自己忽略自己，不能仰賴使用者去改 .gitignore。

    狀態檔裡是使用者的失敗指令，而它落在**使用者的** repo。INSTALL 步驟 11
    有寫「把 .fable/ 加進 .gitignore」，但那只對讀到那一步的人有效——
    一個還沒有 .gitignore 的 repo，下一次 `git add -A` 就把它提交出去。
    """
    repo = _repo(tmp_path)
    _run(repo, _turn("pytest -q", FAIL_OUT))
    ignore = repo / ".fable" / ".gitignore"
    assert ignore.exists(), "狀態目錄沒有自我忽略"
    assert ignore.read_text(encoding="utf-8").strip() == "*"
    out = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                         capture_output=True, text=True).stdout
    assert ".fable" not in out, f"狀態檔仍會被 git 看到：{out}"


def test_g6_stop_hook_active_never_blocks(tmp_path):
    """第二次結束一律放行——gate 不得把 session 卡死。"""
    repo = _repo(tmp_path, {"streak": 1, "shelved": []})
    tp = repo / "transcript.jsonl"
    tp.write_text("".join(json.dumps(e) + "\n" for e in _turn("pytest -q", FAIL_OUT)),
                  encoding="utf-8", newline="")
    assert _run(repo, payload={"transcript_path": str(tp),
                               "stop_hook_active": True}) == ""


# ── 擱置清單 ──────────────────────────────────────────────────────────────
SHELF = {"streak": 0, "shelved": [{
    "id": "goal-111", "first_seen": "2026-09-05 10:00", "streak": 3,
    "last_command": "pytest -q tests/test_x.py", "note": ""}]}


def test_g7_unexplained_shelf_blocks(tmp_path):
    repo = _repo(tmp_path, SHELF)
    out = _run(repo, _turn(assistant_text="did some unrelated work"))
    assert _blocked(out)
    assert "goal-111" in _reason(out)


def test_g8_shelf_with_a_note_stops_blocking(tmp_path):
    """填 note 是一次性動作，做完就永久解除——否則會變成每回合嘮叨。"""
    state = json.loads(json.dumps(SHELF))
    state["shelved"][0]["note"] = "REST 回補在夜盤缺 session 參數，需用戶決定要不要改契約"
    repo = _repo(tmp_path, state)
    assert _run(repo, _turn(assistant_text="did some unrelated work")) == ""


def test_g9_mentioning_the_id_is_not_enough(tmp_path):
    """G9：把 id 講出來**不算**解釋——note 還空著就要繼續擋。

    修復前：提到 id 就放行。而 §4b 明文要求「用戶回來時先把擱置項講出來」，
    於是協議自己教出來的行為就是這道閘的解鎖碼，note 永遠不會被寫。
    與 G8 配對：真正的解除條件只有一個，而且是一次性的——把 note 填上。
    """
    repo = _repo(tmp_path, SHELF)
    out = _run(repo, _turn(assistant_text="goal-111 已擱置，等你拍板"))
    assert _blocked(out), "只提 id 就放行＝這道閘的解鎖碼寫在協議裡"


def test_g14_unreadable_state_is_never_overwritten(tmp_path):
    """G14：state 檔壞掉時不得覆寫——那會把使用者手寫的擱置說明清空。

    實測（2026-09-05）：檔案被截斷後，載入失敗回空狀態、隨即整檔覆寫，
    shelved 全滅且無任何告警。狀態檔不見了是一回事，被靜默改寫是另一回事。
    """
    repo = _repo(tmp_path)
    (repo / ".fable").mkdir(exist_ok=True)
    corrupt = '{"streak": 0, "shel'
    (repo / STATE_REL).write_text(corrupt, encoding="utf-8", newline="")
    out = _run(repo, _turn("pytest -q", FAIL_OUT))
    assert (repo / STATE_REL).read_text(encoding="utf-8") == corrupt, (
        "壞掉的 state 檔被覆寫了——使用者寫的 note 就是這樣消失的"
    )
    # 配對要求：保住資料還不夠，得讓人知道這道閘從此不作用，
    # 否則「保護資料」只是換了一種靜默失效。
    assert _blocked(out), "壞檔時整個組件停擺卻不出聲＝新造的假綠"
    assert "cannot be read" in _reason(out)


def test_g15b_a_real_green_still_clears_the_streak_despite_stray_wording(tmp_path):
    """G15b：G15 的配對——輸出裡別處出現「no tests ran」不得讓真綠燈失效。

    判準的單位是**最後一行摘要**，與失敗判定同一把尺。掃全文時，
    守衛自己印的 `[wiring] no tests ran` 會讓後面的 `12 passed` 不算通過，
    連敗數就永遠清不掉——方向相反的同一個錯。
    """
    repo = _repo(tmp_path, {"streak": 1, "shelved": []})
    mixed = "[wiring] no tests ran\n12 passed in 1.40s\n"
    assert _run(repo, _turn("pytest -q", mixed)) == ""
    assert _state(repo)["streak"] == 0, "真的綠了卻沒歸零"


def test_g15_a_run_with_no_tests_does_not_clear_the_streak(tmp_path):
    """G15：`no tests ran` 是空綠，不得歸零連敗數。

    實測：fail（streak 1）→ `pytest -k nomatch`（no tests ran）→ streak 0
    → 階梯永遠爬不到第 2 階。wiring_runner.sh 對「pytest 零通過」早有守衛，
    本檔當時沒有。空綠既不是通過也不是失敗——它不是一次測試執行。
    """
    repo = _repo(tmp_path, {"streak": 1, "shelved": []})
    assert _run(repo, _turn("pytest -q -k nomatch", "no tests ran in 0.01s\n")) == ""
    assert _state(repo)["streak"] == 1, "空綠把連敗數清掉了"


@pytest.mark.parametrize("cmd,secret", [
    ("GITHUB_TOKEN=ghp_secret123 pytest -q", "ghp_secret123"),
    ("cd sub && GITHUB_TOKEN=ghp_secret123 pytest -q", "ghp_secret123"),
    ("env TOKEN=ghp_secret123 pytest -q", "ghp_secret123"),
    ("pytest -q --db-url=postgres://u:p4ss@h/db", "p4ss"),
])
def test_g16_every_assignment_value_is_masked(tmp_path, cmd, secret):
    """G16：存進 state／回吐進對話的失敗指令，**每一個** `key=value` 的值都要遮。

    只遮開頭的 env 前綴時，`cd r && TOKEN=… pytest`、`env TOKEN=…`、
    `--db-url=postgres://u:p@h` 全部照樣落地——而該字串會寫進使用者 repo 裡的
    檔案，並在每次使用者發話時重新注入對話。鍵保留，所以指令仍認得出來。
    """
    repo = _repo(tmp_path, {"streak": 2, "shelved": []})
    out = _run(repo, _turn(cmd, FAIL_OUT))
    stored = _state(repo)["shelved"][0]["last_command"]
    assert secret not in stored, f"機密落地：{stored}"
    assert secret not in out, f"機密回吐進對話：{out}"
    assert "***" in stored and "pytest" in stored, "遮過頭：指令要仍認得出來"


def test_g10_user_prompt_injects_the_shelf(tmp_path):
    repo = _repo(tmp_path, SHELF)
    out = _run(repo, payload={"hook_event_name": "UserPromptSubmit"})
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert json.loads(out)["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "goal-111" in ctx and "pytest -q tests/test_x.py" in ctx


def test_g11_user_prompt_with_empty_shelf_is_silent(tmp_path):
    repo = _repo(tmp_path, {"streak": 0, "shelved": []})
    assert _run(repo, payload={"hook_event_name": "UserPromptSubmit"}) == ""


# ── 設定與 fail-open ──────────────────────────────────────────────────────
def test_g12_thresholds_are_configurable(tmp_path):
    """門檻是專案相依的（一次測試 3 秒 vs 30 分鐘，容忍度不同）。"""
    repo = _repo(tmp_path, {"streak": 4, "shelved": []})
    out = _run(repo, _turn("pytest -q", FAIL_OUT),
               env={"FABLE_GOAL_ADVERSARIAL_AT": "4", "FABLE_GOAL_SHELVE_AT": "5"})
    assert _blocked(out) and "shelving it" in _reason(out)


@pytest.mark.parametrize("payload", ["not json{", "{}", '{"transcript_path":"/nope"}'])
def test_g13_fails_open(tmp_path, payload):
    repo = _repo(tmp_path)
    out = subprocess.run([sys.executable, GATE], input=payload,
                         capture_output=True, encoding="utf-8", errors="replace",
                         cwd=str(repo), timeout=60)
    assert out.returncode == 0 and out.stdout.strip() == ""


def test_g13_outside_a_git_repo_is_silent(tmp_path):
    """不在 repo 裡就沒有地方放狀態；不得因此報錯或亂寫檔。"""
    d = tmp_path / "plain"
    d.mkdir()
    tp = d / "t.jsonl"
    tp.write_text("".join(json.dumps(e) + "\n" for e in _turn("pytest -q", FAIL_OUT)),
                  encoding="utf-8", newline="")
    out = subprocess.run([sys.executable, GATE],
                         input=json.dumps({"transcript_path": str(tp)}),
                         capture_output=True, encoding="utf-8", errors="replace",
                         cwd=str(d), timeout=60)
    assert out.returncode == 0
