# -*- coding: utf-8 -*-
"""
Stop hook 驗證 gate（verify_gate.py）行為驗收——對應 Fable Protocol Kit「組件3：機械強制驗證」。

驗收項目清單：
  T1 本輪 Edit .py 且無測試執行 → 輸出 {"decision":"block"}，reason 含「測試」
  T2 本輪 Edit .py 且其後有 pytest 執行 → 放行（無輸出、exit 0）
  T3 stop_hook_active=true（第二次結束）→ 即使有未驗證修改也放行（soft gate 防無限迴圈）
  T4 本輪僅 Edit .md（文件檔）→ 放行
  T5 純問答、無任何 Edit/Write → 放行
  T6 transcript_path 不存在 / 內含壞行 → fail-open 放行（gate 絕不可弄壞 session）
  T7 修改發生在上一輪（最後一個真實 user prompt 之前）→ 放行（gate 只看本輪）
  T8 Edit 後出現 <command-name> 類 local-command 條目 → 不得被誤認為新一輪，仍 block
  T9 多生態測試指令（mvn/gradle/dotnet/rspec/phpunit/ctest/make test/tox）→ 識別放行
     （對應 R1 紅隊「全域上線對 Java/C#/Ruby/PHP 專案系統性假攔」發現）
  T10 形似測試的日常指令（cat tox.ini / make testdata / python latest.py 等）→ 仍須 block
     （對應 R4 紅隊「regex 擴充引入假放行面」實證）
  T11 腳本自帶 `--test` 自測入口（python3 tool.py --test）→ 識別放行；
     形似旗標（--test-pypi/--testing/--tests）→ 仍須 block
     （對應 2026-07-05 真實 session 實證：zh_convert_safe.py --test 連續四次被誤攔）
  T12 stdout 為 Windows 傳統編碼（PYTHONIOENCODING=cp950）→ block JSON 仍須完整輸出
     （修復前 reason 首字「⛔」不可編碼 → UnicodeEncodeError 被 fail-open 吞掉
      → gate 靜默失效；主力機實證，失效數日無人察覺）

執行命令：
  cd <repo> && python -m pytest tests/test_verify_gate.py -v

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-07-03 09:56 GMT+8）
══════════════════════════════════════
對應規劃書：Fable Protocol Kit 組件3（Stop hook 驗證 gate，soft 模式）
執行命令：python -m pytest tests/test_verify_gate.py -v

fail-then-pass guard：
  2026-07-02 22:54 對 STUB 版 verify_gate.py（無條件放行）執行
  → 2 failed（T1、T8 期望 block JSON 卻得到空輸出 → JSONDecodeError）, 6 passed
  → 證明測試能抓到「gate 失效（永遠放行）」的錯誤 ✅ guard 正確觸發
  2026-07-03 09:40 T9 對舊 TEST_CMD_RE 執行 → 1 failed：7/8 指令被假攔
  （mvn/gradlew/dotnet/rspec/ctest/make test/tox 全 block；phpunit 案因 .php
  當時不在 CODE_EXTS 而空過＝vacuous pass，如實記錄）→ 擴充 regex + .php 後全綠 ✅
  2026-07-03 09:58 T10 對擴充版 regex 執行 → 1 failed：8/8 形似指令全被誤認為測試
  （tox 裸詞、make testdata、npm run testbed、latest/contest.py、mvn test-compile）
  → 收緊（命令位置錨定 tox/nox、test 詞尾邊界、檔名樣式限縮）後全綠 ✅，T9 同時保持綠
最後執行：2026-07-03 09:56 → 10 passed ✅（全套 33 passed in 1.95s，實測校時）
  2026-07-05 22:50 T11 對舊 TEST_CMD_RE 執行 → 1 failed：3/3 個 --test 自測指令
  被誤攔（allow cases 遭 block）→ regex 加 `\s--test(\s|$)` 錨定後全綠 ✅；
  3 個形似旗標負例（--test-pypi/--testing/--tests）維持 block，T9/T10 保持綠
最後執行：2026-07-05 22:51 → 11 passed ✅（全套 19 passed in 0.65s）

[關鍵量測值]
  T1 block 輸出: {"decision": "block", "reason": "⛔ FABLE-PROTOCOL 驗證 gate：本輪修改了程式碼（app.py）..."}
  T2/T4/T5/T6/T7 stdout 長度 = 0, returncode = 0
  T3 stop_hook_active=true → stdout 長度 = 0（soft 放行）
  T8 block 輸出含 app.py，local-command 條目未重置輪次邊界

✅ 已驗收（本檔涵蓋）
  T1 → block JSON 正確產出，reason 含「測試」與檔名
  T2 → pytest 命令被 TEST_CMD_RE 識別，放行
  T3 → soft 模式第二次結束放行
  T4 → .md 不在 CODE_EXTS，放行
  T5 → 無工具呼叫，放行
  T6 → 路徑不存在 + 壞 JSON 行皆 fail-open
  T7 → 輪次邊界（最後真實 user prompt）判定正確
  T8 → <command-name>/<local-command-*> 前綴條目不算輪次邊界
⏳ 待驗收（本檔未涵蓋）
  真實 Stop 事件端到端觸發：需在互動 session 中讓模型改碼後結束才能觀察，
  無法以 claude -p 穩定重現（-p 模式模型行為不可控）；解鎖條件＝佈署後
  以真實互動 session 手動演練一次（改一行 .py 不跑測試即結束，應見擋回訊息）。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "verify_gate.py"


def _user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def _tool_use(name, tool_input):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "toolu_x", "name": name, "input": tool_input}]}}


def _tool_result():
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_x", "content": "ok"}]}}


def run_gate(tmp_path, entries, stop_hook_active=False, transcript_path=None):
    """以生產介面（stdin JSON → stdout）呼叫 gate，回傳 (stdout, returncode)。"""
    if transcript_path is None:
        transcript_path = tmp_path / "transcript.jsonl"
        transcript_path.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in entries),
            encoding="utf-8")
    payload = json.dumps({
        "session_id": "test", "hook_event_name": "Stop",
        "stop_hook_active": stop_hook_active,
        "transcript_path": str(transcript_path)})
    proc = subprocess.run([sys.executable, str(GATE)], input=payload,
                          capture_output=True, text=True, encoding="utf-8", timeout=30)
    return proc.stdout.strip(), proc.returncode


def test_t1_edit_py_without_test_blocks(tmp_path):
    entries = [
        _user("幫我修 bug"),
        _tool_use("Edit", {"file_path": "D:\\proj\\app.py", "old_string": "a", "new_string": "b"}),
        _tool_result(),
    ]
    out, rc = run_gate(tmp_path, entries)
    assert rc == 0
    data = json.loads(out)
    assert data["decision"] == "block"
    assert "測試" in data["reason"]
    assert "app.py" in data["reason"]


def test_t2_edit_py_with_pytest_allows(tmp_path):
    entries = [
        _user("幫我修 bug"),
        _tool_use("Edit", {"file_path": "D:\\proj\\app.py", "old_string": "a", "new_string": "b"}),
        _tool_result(),
        _tool_use("Bash", {"command": "python -m pytest tests/ -v"}),
        _tool_result(),
    ]
    out, rc = run_gate(tmp_path, entries)
    assert rc == 0
    assert out == ""


def test_t3_stop_hook_active_soft_allows(tmp_path):
    entries = [
        _user("幫我修 bug"),
        _tool_use("Edit", {"file_path": "D:\\proj\\app.py", "old_string": "a", "new_string": "b"}),
        _tool_result(),
    ]
    out, rc = run_gate(tmp_path, entries, stop_hook_active=True)
    assert rc == 0
    assert out == ""


def test_t4_md_only_edit_allows(tmp_path):
    entries = [
        _user("改一下說明文件"),
        _tool_use("Write", {"file_path": "D:\\proj\\README.md", "content": "x"}),
        _tool_result(),
    ]
    out, rc = run_gate(tmp_path, entries)
    assert rc == 0
    assert out == ""


def test_t5_pure_qa_allows(tmp_path):
    entries = [_user("這段程式在做什麼？")]
    out, rc = run_gate(tmp_path, entries)
    assert rc == 0
    assert out == ""


def test_t6_missing_or_corrupt_transcript_fails_open(tmp_path):
    out, rc = run_gate(tmp_path, [], transcript_path=tmp_path / "nonexistent.jsonl")
    assert rc == 0
    assert out == ""
    corrupt = tmp_path / "corrupt.jsonl"
    corrupt.write_text('{"type":"user","message":{"content":"hi"}}\nNOT-JSON-LINE\n',
                       encoding="utf-8")
    out, rc = run_gate(tmp_path, [], transcript_path=corrupt)
    assert rc == 0
    assert out == ""


def test_t7_edit_in_previous_turn_allows(tmp_path):
    entries = [
        _user("上一輪：修 bug"),
        _tool_use("Edit", {"file_path": "D:\\proj\\app.py", "old_string": "a", "new_string": "b"}),
        _tool_result(),
        _user("本輪：解釋一下剛剛改了什麼"),
    ]
    out, rc = run_gate(tmp_path, entries)
    assert rc == 0
    assert out == ""


def test_t8_local_command_entry_not_turn_boundary(tmp_path):
    entries = [
        _user("幫我修 bug"),
        _tool_use("Edit", {"file_path": "D:\\proj\\app.py", "old_string": "a", "new_string": "b"}),
        _tool_result(),
        _user("<command-name>/model</command-name>"),
        _user("<local-command-stdout>Set model to X</local-command-stdout>"),
    ]
    out, rc = run_gate(tmp_path, entries)
    assert rc == 0
    data = json.loads(out)
    assert data["decision"] == "block"
    assert "app.py" in data["reason"]


def test_t9_multi_ecosystem_test_commands_allow(tmp_path):
    """T9：非 Python/JS 生態的測試指令必須被 TEST_CMD_RE 識別（R1 紅隊：全域假攔面）。"""
    cases = [
        ("D:\\proj\\App.java", "mvn clean test"),
        ("D:\\proj\\App.java", "./gradlew test --info"),
        ("D:\\proj\\Service.cs", "dotnet test MySolution.sln"),
        ("D:\\proj\\model.rb", "bundle exec rspec spec/models"),
        ("D:\\proj\\Handler.php", "vendor/bin/phpunit tests/"),
        ("D:\\proj\\algo.c", "ctest --output-on-failure"),
        ("D:\\proj\\util.c", "make test"),
        ("D:\\proj\\lib.py", "tox -e py311"),
    ]
    failures = []
    for path, cmd in cases:
        entries = [
            _user("幫我修 bug"),
            _tool_use("Edit", {"file_path": path, "old_string": "a", "new_string": "b"}),
            _tool_result(),
            _tool_use("Bash", {"command": cmd}),
            _tool_result(),
        ]
        out, rc = run_gate(tmp_path, entries)
        if rc != 0 or out != "":
            failures.append((cmd, out[:60]))
    assert not failures, f"以下測試指令未被識別而遭假攔: {failures}"


def test_t10_nontest_commands_still_block(tmp_path):
    """T10：形似測試的日常指令不得被誤認為測試（R4 紅隊：假放行面實證）。"""
    cases = [
        "cat tox.ini",
        "pip install tox",
        "git commit -m 'refactor tox config'",
        "make testdata",
        "npm run testbed",
        "python latest.py",
        "python contest.py",
        "mvn test-compile",
    ]
    failures = []
    for cmd in cases:
        entries = [
            _user("幫我修 bug"),
            _tool_use("Edit", {"file_path": "D:\\proj\\app.py", "old_string": "a", "new_string": "b"}),
            _tool_result(),
            _tool_use("Bash", {"command": cmd}),
            _tool_result(),
        ]
        out, rc = run_gate(tmp_path, entries)
        blocked = False
        if out:
            try:
                blocked = json.loads(out).get("decision") == "block"
            except json.JSONDecodeError:
                blocked = False
        if rc != 0 or not blocked:
            failures.append(cmd)
    assert not failures, f"以下非測試指令被誤認為測試（假放行）: {failures}"


def test_t11_selftest_flag_allow(tmp_path):
    """T11：腳本自帶 `--test` 自測入口須被識別為測試執行（2026-07-05 實證：
    zh_convert_safe.py --test 於真實 session 連續四次被 gate 誤攔）；
    形似旗標（--test-pypi/--testing/--tests）不得因此假放行。"""
    allow_cases = [
        ("D:\\proj\\tool.py", "python3 zh_convert_safe.py --test"),
        ("D:\\proj\\tool.py", "python3 SKILL/pdf-ocr/zh_convert_safe.py --test && git add -u"),
        ("D:\\proj\\cli.rs", "./target/release/mytool --test"),
    ]
    block_cases = [
        "pip install --test-pypi somepkg",
        "./deploy.sh --testing",
        "cargo build --tests",
    ]
    failures = []
    for path, cmd in allow_cases:
        entries = [
            _user("幫我修 bug"),
            _tool_use("Edit", {"file_path": path, "old_string": "a", "new_string": "b"}),
            _tool_result(),
            _tool_use("Bash", {"command": cmd}),
            _tool_result(),
        ]
        out, rc = run_gate(tmp_path, entries)
        if rc != 0 or out != "":
            failures.append(("應放行未放行", cmd, out[:60]))
    for cmd in block_cases:
        entries = [
            _user("幫我修 bug"),
            _tool_use("Edit", {"file_path": "D:\\proj\\app.py", "old_string": "a", "new_string": "b"}),
            _tool_result(),
            _tool_use("Bash", {"command": cmd}),
            _tool_result(),
        ]
        out, rc = run_gate(tmp_path, entries)
        blocked = False
        if out:
            try:
                blocked = json.loads(out).get("decision") == "block"
            except json.JSONDecodeError:
                blocked = False
        if not blocked:
            failures.append(("應攔未攔", cmd, out[:60]))
    assert not failures, f"T11 失敗: {failures}"


def test_t12_cp950_stdout_still_blocks(tmp_path):
    """T12：stdout 為 Windows 傳統編碼（cp950）時 block JSON 仍須完整輸出。
    修復前：reason 首字「⛔」不可編碼 → print 拋 UnicodeEncodeError → fail-open 吞掉
    → gate 靜默失效（主力機實證）。修復＝main() 開頭 reconfigure utf-8。"""
    entries = [
        _user("幫我修 bug"),
        _tool_use("Edit", {"file_path": "D:\\proj\\app.py", "old_string": "a", "new_string": "b"}),
        _tool_result(),
    ]
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries), encoding="utf-8")
    payload = json.dumps({  # ensure_ascii 預設 → payload 純 ASCII，不受 stdin 編碼影響
        "session_id": "test", "hook_event_name": "Stop",
        "stop_hook_active": False, "transcript_path": str(transcript)})
    env = {**os.environ, "PYTHONIOENCODING": "cp950"}
    env.pop("PYTHONUTF8", None)
    proc = subprocess.run([sys.executable, str(GATE)], input=payload.encode("ascii"),
                          capture_output=True, timeout=30, env=env)
    assert proc.returncode == 0
    data = json.loads(proc.stdout.decode("utf-8").strip())
    assert data["decision"] == "block"
    assert data["reason"].startswith("⛔")
