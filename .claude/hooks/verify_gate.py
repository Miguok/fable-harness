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
import os
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
    r"|npm\s+(run\s+)?test(?:[:._-][\w:.-]*)?|yarn\s+test(?:[:._-][\w:.-]*)?|pnpm\s+(run\s+)?test(?:[:._-][\w:.-]*)?|bun\s+test\b|node\s+--test"
    r"|go\s+test|cargo\s+test|\bvitest\b|\bjest\b"
    r"|mvnw?(\.cmd)?\s+(\S+\s+)*test(\s|$)|gradlew?(\.bat)?\s+(\S+\s+)*test(\s|$)|dotnet\s+test(\s|$)"
    r"|\brspec\b|\bphpunit\b|\bctest\b|make\s+test\b|rake\s+(\S+\s+)*test\b|mix\s+test\b"
    r"|(^|[;&|]\s*)(tox|nox)\b|deno\s+test|rails\s+test"
    # 腳本自帶 --test 自測入口（2026-07-05 T11：zh_convert_safe.py --test 真實
    # session 連續誤攔實證）；(\s|$) 錨定使 --tests/--testing/--test-pypi 不假放行
    r"|\s--test(\s|$))"
    # 與 goal_gate 的同一條尾界：路徑裡的 `pytest`／`jest` 不得被當成測試指令。
    # 兩份必須同時改——2026-09-06 只改了一份，於是同一條 `./gradlew test --info`
    # 在兩支 hook 得到相反的答案，而 verify_gate 的測試還釘住了其中一個。
    # `(?<=\s)` 那一半處理「分支自己吃掉了空白」的情形，見 goal_gate 的說明。
    r"(?:(?<=\s)|(?![\w-]|[/" + "\\\\" + r"]))",
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
# harness 注入的東西。清單由本機 200 份真實 transcript 取樣得出，不是憑想像列的
# ——尤其 `Stop hook feedback:` 是**閘自己的擋人訊息**，把它當成新回合的開始，
# 等於閘一邊擋人一邊把自己的擋人讀成「使用者回來了」。
LOCAL_COMMAND_PREFIXES = (
    "<command-name>", "<local-command-stdout>",
    "<local-command-stderr>", "<local-command-caveat>",
    "Stop hook feedback:", "<task-notification>",
    "[Request interrupted", "[SYSTEM NOTIFICATION",
)


def is_real_user_prompt(entry):
    """這一則是不是使用者真的打的字。

    ⚠ **真實的 transcript 裡使用者輸入是 list 形，不是字串。** 原本的
    `not isinstance(content, str) → False` 註解寫「tool_result 列表不是真實
    prompt」，那句只對了一半：list 形**同時**承載 tool_result 與真實輸入，
    而字串形承載的幾乎全是 harness 注入。2026-09-06 掃本機 200 份 transcript：
    list/text 436 筆（427 筆是真實輸入）、str 539 筆（幾乎全是 hook 回饋與
    背景通知）。於是這個判定在生產環境是**反的**——回合視窗不前進。

    與 `goal_gate.py` 的 `prompt_text` 同一套判準；那裡是這段邏輯的正本，
    此處刻意重寫而非 import，因為兩支 hook 必須各自獨立可執行。
    """
    if entry.get("type") != "user":
        return False
    # `isMeta`／`isCompactSummary` 是產品自己給的旗標，標記 harness 注入。
    # 載入 skill 會產生 `isMeta: true` 的條目，拿文字開頭猜會把它當成新回合。
    # 與 goal_gate 的 `prompt_text` 同一套判準。
    if entry.get("isMeta") or entry.get("isCompactSummary"):
        return False
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False  # 工具回覆不是使用者輸入
        text = "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    else:
        return False
    if not text.strip():
        return False
    return not text.lstrip().startswith(LOCAL_COMMAND_PREFIXES)


MAX_LISTED_FILES = 12   # 擋人訊息最多列幾個檔名


def one_line(value, limit):
    """把一個檔名壓成單行再截斷——與 `goal_gate.one_line` 同一條規則。

    這段訊息會原封不動注入下一回合的對話，而檔名來自 transcript，是**模型自己
    寫過的字**。`file_path` 裡塞一個換行，就能在資料區裡自己寫一行
    「（以上為 gate 訊息結束）」把後面的內容推到框架之外；不設上限則是同一個
    洞的另一半——一輪改一百個檔，擋人訊息就變成一整螢幕。

    `goal_gate` 這一輪已經為擱置項補上同樣的處理，這裡漏掉：同一類沒掃完，
    而這是這個類別的第三個實例（前兩個是注入 repo 檔名與注入擱置備註）。
    """
    text = str(value if value is not None else "")
    return " ".join(text.split())[:limit]


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


QUIET_PER_LABEL = 20      # 同一個標籤最多幾行
# 數行時最多讀多少。**它防的不是自家的成長**——標籤空間是封閉的（15 個字面
# 標籤 × 20 行 ≈ 31 KB），自家寫入者永遠碰不到 1 MB。它防的是**別人污染這個
# 檔**：`.gate_fail` 可以被 `git add -f` 提交進一個會收 PR 的 repo，而每一次
# fail-open 都要把它讀一遍數行數（實測 90 MB 要 0.32 秒）。
# ⚠ 它**是**一個全域上限：檔案超過這個大小之後，三支 gate 的屍檢全部停寫。
# 那是刻意的取捨（被污染的檔已經沒有診斷價值，而每次 fail-open 讀 90 MB 更糟），
# 但不要再說「沒有全域上限」——第一版的 docstring 那樣寫，與這一行矛盾。
QUIET_MAX_SCAN = 1 << 20


def _quiet_lock(fd, release=False):
    """對**獨立的鎖檔**取／放獨佔鎖——拿不到就算了，絕不阻塞超過約 0.1 秒。

    `O_APPEND` 在 Windows **不是原子的**：MSVCRT 的實作是 lseek(END) 之後再
    WriteFile，兩步之間別的行程可以插進來。實測三個行程對齊起跑各寫一行、
    20 次試驗 **10 次掉筆**，還產生被切掉開頭的殘行。

    ⚠ **鎖的對象是 `.gate_fail.lock`，不是 `.gate_fail` 本身。** 第一版直接鎖
    資料檔的第 0 byte，而 Windows 的 `msvcrt.locking` 是**強制鎖**不是勸告鎖：
    重試耗盡之後程式繼續走到 `os.read`，那個讀取踩到被鎖的 byte → PermissionError
    → 被最外層的 except 吞掉，**一個字都沒寫**。docstring 當時寫「等不到就照寫，
    遺失一行遙測比卡住一個回合便宜」，而 Windows 上的實際行為是整筆消失——
    也就是說這個機制自己犯了它要治的病（2026-09-06 抗辯實測：鎖被別的行程持有
    時 `note_quiet` 0.137 秒回來、victim 那筆不在檔案裡）。
    改鎖獨立的檔案之後，讀寫資料檔完全不碰被鎖的區域，「拿不到鎖就照寫」才是真的。

    用短暫的非阻塞重試而不是阻塞式鎖：hook 的 timeout 是 5～15 秒，阻塞式
    `msvcrt.locking` 會等到 10 秒才放棄，那會把「掉一行屍檢」升級成「hook 逾時」。
    ⚠ POSIX 分支第一版寫的是 `flock(fd, LOCK_EX)`——**沒有 LOCK_NB**，也就是
    無上限阻塞，正好是上一句禁止的事（同一輪抗辯指出；本機沒有 POSIX 環境可以
    實跑，是讀碼認定的）。現在兩邊都是有界的非阻塞重試。
    """
    try:
        deadline = 0.1
        if os.name == "nt":
            import msvcrt
            import time as _t
            if release:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                return True
            end = _t.time() + deadline
            while _t.time() < end:
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    return True
                except OSError:  # quiet-ok: 鎖被別人持有是正常的，重試就好
                    _t.sleep(0.002)
            return False
        import fcntl
        import time as _t
        if release:
            fcntl.flock(fd, fcntl.LOCK_UN)
            return True
        end = _t.time() + deadline
        while _t.time() < end:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except OSError:  # quiet-ok: 同上，非阻塞重試
                _t.sleep(0.002)
        return False
    except Exception:  # quiet-ok: 鎖機制本身壞掉就不鎖，照寫，絕不阻塞 session
        return False


def note_quiet(label, exc=None, count=None):
    """把一次「閘判不出來／自己壞掉」寫成一行，落在同目錄的 `.gate_fail`。

    **fail-open 沒問題，安靜的 fail-open 才是問題。** 每一條 fail-open 在外部
    看起來都和「一切正常」一模一樣，所以它們可以壞掉好幾天而沒有人發現。

    契約（三支 hook 各有一份，由 tests/test_no_silent_gate.py 綁在一起）：
      - 絕不拋例外——遙測自己壞掉不得破壞 fail-open
      - 一行的格式固定為 `<ISO 時間戳> <gate>/<label>: <例外類別>[ ×N]`
      - **只寫標籤與例外類別，不寫 payload**。這條不變式必須是**結構性**的，
        不能靠呼叫端自律：`label` 由呼叫端提供但只該是字面字串，而第三個參數
        限定成**整數**（`count`）。⚠ 它上一版叫 `detail` 且收任意字串，於是
        「不寫 payload」又退回成一句註解——實測把某個呼叫點改成
        `detail=str(exc)` 就把絕對路徑寫進檔案，全套 390 passed 無人叫，
        而那一行開頭是合法時間戳，會原樣通過注入器的白名單（2026-09-06 抗辯）。
      - 標籤前面掛**這支 gate 的檔名**：四個呼叫點都叫 `main`，而三支共用同一個
        檔，否則觸發最頻繁的那支會餓死其他兩支。
      - 同一個標籤最多 `QUIET_PER_LABEL` 行。
      - 比對是**整段相等或後接空白**，不是純 `startswith`：鍵的結尾是例外類別
        名，而 `Exception`／`ExceptionGroup`、`BaseException`／`BaseExceptionGroup`
        是 stdlib 真實存在的前綴對。⚠ 我在上一個 commit 寫「構造不出真實案例」，
        那句話只檢查了標籤段、沒檢查例外類別段，是錯的（同一輪抗辯指出）。
    """
    try:
        from datetime import datetime, timezone
        here = os.path.dirname(os.path.abspath(__file__))
        marker = os.path.join(here, ".gate_fail")
        gate = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
        key = "%s/%s: %s" % (gate, " ".join(str(label).split())[:100],
                             type(exc).__name__ if exc is not None else "-")
        text = key + ((" x%d" % int(count)) if count is not None else "")
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
        lfd = os.open(marker + ".lock", flags, 0o600)
        try:
            _quiet_lock(lfd)
            fd = os.open(marker, flags, 0o600)
            try:
                try:
                    body = os.read(fd, QUIET_MAX_SCAN)
                except OSError:  # quiet-ok: 數不了就不數，直接寫，見下方說明
                    # 數不了就不數，直接寫。別的行程（防毒、索引器，或任何用
                    # 限制性 sharing 開這個檔的東西）在 Windows 上會讓這個讀取
                    # 拋 PermissionError；讓它冒到外層就是**整筆消失**，而
                    # docstring 承諾的是「拿不到就照寫」。重複一行遠比消失一行好
                    # ——屍檢的用途是「有東西壞著」，不是精確計數（2026-09-06 抗辯）。
                    body = b""
                if len(body) >= QUIET_MAX_SCAN:
                    return  # 大到數不完就別再寫了；這種檔早該被人處理掉
                seen = 0
                for raw in body.decode("utf-8", "replace").split("\n"):
                    part = raw.split(" ", 1)
                    if len(part) == 2 and (part[1] == key
                                           or part[1].startswith(key + " ")):
                        seen += 1
                if seen < QUIET_PER_LABEL:
                    os.lseek(fd, 0, os.SEEK_END)
                    os.write(fd, ("%s %s\n" % (
                        datetime.now(timezone.utc).isoformat(),
                        text)).encode("utf-8"))
            finally:
                os.close(fd)
        finally:
            _quiet_lock(lfd, release=True)
            os.close(lfd)
    except Exception:  # quiet-ok: 遙測自身故障不得破壞 fail-open，這裡沒有第二個出口
        pass


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
        torn = 0
        with open(data["transcript_path"], encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:  # quiet-ok: 整趟結束後記一次，見下方
                    torn += 1
        if torn:
            # ⚠ 原本標著「壞一行不影響判定」，那句話是假的：把帶著測試指令的
            # 那一行截斷，這道閘就從**放行翻成擋人**——它看到「改了碼、沒跑測試」。
            # 實測（2026-09-06 抗辯指出，我重現）：完整 blocked=False、
            # 同一份只截斷那一行 blocked=True。方向是誤擋，而誤擋掛在一道硬閘上。
            # 記一次而不是逐行記：逐行會把屍檢灌爆，真正的失效反而寫不進去。
            note_quiet("transcript 有行讀不動，這一輪的判定可能不完整", count=torn)
        edited, test_seen = analyze(entries)
        if edited and not test_seen:
            files = "、".join(one_line(n, 80) for n in
                             list(dict.fromkeys(edited))[:MAX_LISTED_FILES])
            print(json.dumps({
                "decision": "block",
                "reason": (
                    f"⛔ FABLE-PROTOCOL 驗證 gate：本輪修改了程式碼（{files}）"
                    "但未偵測到自動化測試執行。請補跑對應測試並附 fail-then-pass 證據後再結束；"
                    "若本輪確實不需測試（中途暫停、實驗性修改），請向用戶說明原因後再次結束即可放行。"
                ),
            }, ensure_ascii=False))
    except Exception as exc:
        note_quiet("main", exc)  # fail-open：不阻斷 session，但留下屍檢
    return 0


if __name__ == "__main__":
    sys.exit(main())
