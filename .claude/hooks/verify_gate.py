# -*- coding: utf-8 -*-
"""
Stop hook 驗證 gate（FABLE-PROTOCOL 組件3，soft 模式）。

行為：解析 transcript，若「最後一個真實 user prompt 之後」有 Edit/Write/NotebookEdit
修改程式碼檔，卻沒有任何測試執行命令，輸出 {"decision":"block","reason":...} 擋回一次；
stop_hook_active=true（模型第二次結束）時放行，避免純討論 session 被無限卡死。
任何解析錯誤一律 fail-open（exit 0 無輸出）——gate 絕不可弄壞 session；但 fail-open 前
會 best-effort 留一行屍檢到同目錄 .gate_fail（gitignored），否則靜默死亡數日無人察覺。

介面：stdin 收 hook JSON（transcript_path / stop_hook_active），stdout 輸出 block JSON 或無輸出。
測試：tests/test_verify_gate.py（十二案例，fail-then-pass 已驗證；T9 多生態識別、T10 假放行防護、
T11 --test 自測入口、T12 fail-open 屍檢遙測且 sanitize 不倒 payload）。
"""
import json
import re
import sys
from pathlib import Path, PurePath

CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs",
    ".sh", ".ps1", ".psm1", ".vbs",
    ".go", ".rs", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".sql", ".php",
}

TEST_CMD_RE = re.compile(
    r"(pytest"
    r"|python[3]?(\.exe)?\s+(-m\s+unittest|(\S*[/\\])?(test\S*\.py|\S*_test\.py))"
    r"|npm\s+(run\s+)?test\b|yarn\s+test\b|pnpm\s+(run\s+)?test\b|bun\s+test\b|node\s+--test"
    r"|go\s+test|cargo\s+test|\bvitest\b|\bjest\b"
    r"|mvnw?(\.cmd)?\s+(\S+\s+)*test(\s|$)|gradlew?(\.bat)?\s+(\S+\s+)*test(\s|$)|dotnet\s+test(\s|$)"
    r"|\brspec\b|\bphpunit\b|\bctest\b|make\s+test\b|rake\s+(\S+\s+)*test\b|mix\s+test\b"
    r"|(^|[;&|]\s*)(tox|nox)\b|deno\s+test|rails\s+test"
    # 腳本自帶 --test 自測入口（2026-07-05 T11：zh_convert_safe.py --test 真實
    # session 連續誤攔實證）；(\s|$) 錨定使 --tests/--testing/--test-pypi 不假放行
    r"|\s--test(\s|$))",
    re.IGNORECASE,
)

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}

# 改碼不是只走 Edit/Write——2026-08-27 對近 30 份真實 transcript 量測：
#   Bash 6989 次 vs Edit 813 + Write 387；其中「改檔形態」（sed -i／重導向／tee／cat >）887 次。
#   也就是說**約三分之一的程式碼變更完全不在 gate 的偵測範圍內**。
#   （同批量測：MultiEdit 在 103 份 transcript 中只出現在 4 份、近 30 份 0 次，故不納入 EDIT_TOOLS。）
# 只認「寫入目標」本身是程式碼檔的情形，避免 `grep foo bar.py > out.txt` 這種讀 .py、寫別處的誤攔。
_REDIRECT_OR_TEE_RE = re.compile(
    r"(?:>>?|\btee\b(?:\s+-a)?)\s*['\"]?([^\s'\";|&<>]+)"
)
# sed -i 的檔名在最後，前面還夾著 script 參數，故單獨抓該片段的尾端 token。
_SED_INPLACE_RE = re.compile(
    # 貪婪（非 lazy）是刻意的：sed 的檔名在最後，lazy 會停在 script 參數上（實測 's/a/b/' 被當成檔名）
    r"\bsed\b(?:\s+-[^\s]+)*\s+-i(?:\.\w+)?\b[^|;&\n]*\s+['\"]?([^\s'\";|&<>]+)"
)
# 暫存區不算專案程式碼：寫 scratchpad 的一次性腳本不該觸發 gate。
_TEMP_MARKERS = ("/tmp/", "\\temp\\", "/temp/", "scratchpad", "appdata", "\\tmp\\")


def shell_written_code_files(command):
    """回傳這道 shell 命令寫入的程式碼檔名（沒有就空列表）。

    只看寫入目標的副檔名，不看命令裡出現過哪些檔——讀 .py 而寫 .txt 不算改碼。
    """
    written = []
    for pattern in (_REDIRECT_OR_TEE_RE, _SED_INPLACE_RE):
        for target in pattern.findall(command):
            lowered = target.lower()
            if any(marker in lowered for marker in _TEMP_MARKERS):
                continue
            if PurePath(target).suffix.lower() in CODE_EXTS:
                written.append(PurePath(target).name)
    return written
LOCAL_COMMAND_PREFIXES = (
    "<command-name>", "<local-command-stdout>",
    "<local-command-stderr>", "<local-command-caveat>",
)


def is_real_user_prompt(entry):
    if entry.get("type") != "user":
        return False
    content = entry.get("message", {}).get("content")
    if not isinstance(content, str):
        return False  # tool_result 列表不是真實 prompt
    return not content.lstrip().startswith(LOCAL_COMMAND_PREFIXES)


def iter_tool_uses(entries):
    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                yield block.get("name", ""), block.get("input", {}) or {}


def analyze(entries):
    """回傳 (本輪修改的程式碼檔名列表, 是否偵測到測試執行)。"""
    last_prompt_idx = -1
    for i, entry in enumerate(entries):
        if is_real_user_prompt(entry):
            last_prompt_idx = i
    current_turn = entries[last_prompt_idx + 1:]

    edited, test_seen = [], False
    for name, tool_input in iter_tool_uses(current_turn):
        if name in EDIT_TOOLS:
            path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
            if PurePath(path).suffix.lower() in CODE_EXTS:
                edited.append(PurePath(path).name)
        elif name in SHELL_TOOLS:
            command = tool_input.get("command", "")
            if TEST_CMD_RE.search(command):
                test_seen = True
            edited.extend(shell_written_code_files(command))
    return edited, test_seen


def _record_failure(exc):
    """fail-open 前 best-effort 留一行屍檢到同目錄 .gate_fail：沒有遙測的靜默 fail-open
    會數日無人察覺（cp950 事故即此模式——print 拋錯被 except 吞掉、gate 靜默不 block）。
    只記「例外類別 + 截斷訊息」（非 exc!r/整包 payload，降低未來例外把路徑/內容寫入的風險）；
    容量上限保留最早的事故行（首次靜默死亡最有價值），滿了即停寫、不淘汰不覆寫；
    整段包在自己的 try 內——遙測本身故障絕不可破壞 fail-open。"""
    try:
        from datetime import datetime, timezone
        marker = Path(__file__).resolve().parent / ".gate_fail"
        max_lines = 500
        if marker.exists():
            with open(marker, encoding="utf-8", errors="replace") as f:
                if sum(1 for _ in f) >= max_lines:
                    return  # 上限：保留最早事故行，不 truncate、不 evict-oldest
        ts = datetime.now(timezone.utc).isoformat()
        msg = str(exc)[:200].replace("\n", " ").replace("\r", " ")
        with open(marker, "a", encoding="utf-8") as f:
            f.write(f"{ts} {type(exc).__name__}: {msg}\n")
    except Exception:
        pass  # 遙測自身故障照樣 fail-open


def main():
    try:
        # Claude Code reads hook stdout as UTF-8; on legacy-codepage Windows
        # (e.g. cp950) the default encoding makes print() raise on "⛔"/CJK,
        # which the fail-open except swallows — the gate then never blocks.
        sys.stdout.reconfigure(encoding="utf-8")
        data = json.loads(sys.stdin.read() or "{}")
        if data.get("stop_hook_active"):
            return 0
        entries = []
        with open(data["transcript_path"], encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        edited, test_seen = analyze(entries)
        if edited and not test_seen:
            files = "、".join(dict.fromkeys(edited))
            print(json.dumps({
                "decision": "block",
                "reason": (
                    f"⛔ FABLE-PROTOCOL 驗證 gate：本輪修改了程式碼（{files}）"
                    "但未偵測到自動化測試執行。請補跑對應測試並附 fail-then-pass 證據後再結束；"
                    "若本輪確實不需測試（中途暫停、實驗性修改），請向用戶說明原因後再次結束即可放行。"
                ),
            }, ensure_ascii=False))
    except Exception as exc:
        _record_failure(exc)  # fail-open：gate 自身故障不得阻斷 session，但留屍檢可見
    return 0


if __name__ == "__main__":
    sys.exit(main())
