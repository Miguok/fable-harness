# -*- coding: utf-8 -*-
"""P0.5 harness / workflow 只讀偵測器（ROADMAP.md §4.1 為權威 spec）。

定位：只讀——不建立、不修改、不刪除任何檔案，不動 settings.json 與全域 CLAUDE.md。
輸出單一 JSON 物件到 stdout，供人或上層流程判讀是否已有專用開發 harness
（harnessmith / Superpowers / 其他 generic harness）在跑，不自動接管、不自動停用 Fable。

用法：
  python scripts/detect_harness.py <project-root>

輸出 exit code：
  0 — 偵測完成，JSON 印在 stdout。
  2 — <project-root> 不存在或不是目錄，錯誤訊息印在 stderr，stdout 不印半殘 JSON。

三層訊號（逐一對應 ROADMAP §4.1 原文）：
  Layer 1 明確工具（命中即 high）：
    .harnessmith/、harnessmith.toml、.superpowers/、
    skills/using-superpowers/SKILL.md、.claude/skills/using-superpowers/SKILL.md
  Layer 2 通用 harness 結構訊號：
    skills/、.claude/skills/、.agents/skills/、.claude/hooks/、.claude/workflows/、
    specs/、AGENTS.md、CLAUDE.md、GEMINI.md
  Layer 3 內容關鍵字（只掃頂層 CLAUDE.md / AGENTS.md / GEMINI.md / README.md / ROADMAP.md，
    各檔讀取上限 64KB，大小寫不敏感，整詞/整詞組匹配避免誤傷）：
    harness、workflow、agentic、SDD、BDD、TDD、subagent、reviewer、planning、
    brainstorming、unattended、finish branch

計分規則：
  high   = 命中任一 Layer 1 訊號。
  medium = 無 Layer 1，且 Layer 2 結構訊號命中數 >= 2（如 skills + hooks）。
  low    = 無 Layer 1，且（僅命中 1 個 Layer 2 結構訊號，如只有 CLAUDE.md；
           或無 Layer 2 訊號、僅命中 Layer 3 關鍵字，candidate 記為 unknown-workflow）。
  none   = 三層皆無命中（無足夠 evidence）。
  註（2026-07-05 抗辯定案）：Layer 3 內容關鍵字「不會」把單一 Layer 2 訊號升為 medium。
    依 ROADMAP §4.1「low＝僅單一弱訊號（如只有 CLAUDE.md）」，而 workflow/TDD/planning/
    reviewer 等關鍵字在普通專案的 CLAUDE.md/README 極常見，若據以升 medium 會對正常專案
    誤觸 ask-user 中斷。Layer 3 僅用於「無任何 Layer 2 訊號」時標記 unknown-workflow（low）。
  已知限制：內容關鍵字採 \b 詞邊界，繁中「中文緊貼英文詞」（如「workflow設計」無空格）
    會漏抓（false negative，偏安全）；本版不處理 CJK 邊界，見測試 ⏳ 區。

candidate 命名：
  .harnessmith/ 或 harnessmith.toml → harnessmith
  .superpowers/ 或 using-superpowers/SKILL.md → superpowers
  有 Layer 2 結構訊號但無具名工具 → generic-harness
  僅 Layer 3 內容關鍵字（無 Layer 2） → unknown-workflow

recommendation 映射：
  high → use-detected-harness-as-main-flow
  medium → ask-user
  low → no-special-routing
  none → no-special-routing
  （以上 3 值為 recommendation 的全部輸出值；spec 於 2026-07-05 抗辯＋GPT 二審後移除原第 4
  個死值，enum 不再保留無觸發條件的項目。）
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Layer 1：明確工具訊號（命中任一即 high）
LAYER1_HARNESSMITH = [
    (".harnessmith", "dir"),
    ("harnessmith.toml", "file"),
]
LAYER1_SUPERPOWERS = [
    (".superpowers", "dir"),
    ("skills/using-superpowers/SKILL.md", "file"),
    (".claude/skills/using-superpowers/SKILL.md", "file"),
]

# Layer 2：通用 harness 結構訊號（medium 需 >=2 個命中；單一命中僅 low）
LAYER2_SIGNALS = [
    ("skills", "dir"),
    (".claude/skills", "dir"),
    (".agents/skills", "dir"),
    (".claude/hooks", "dir"),
    (".claude/workflows", "dir"),
    ("specs", "dir"),
    # 以下 .md 屬 Layer2 但為「弱訊號」：單獨命中只到 low，需與其他 Layer2 湊滿 >=2 才 medium。
    # 未來 item（見 ROADMAP §4.1）：真實誤觸偏多時，考慮把這三個 .md 拆為獨立弱訊號類、不計入門檻。
    ("AGENTS.md", "file"),
    ("CLAUDE.md", "file"),
    ("GEMINI.md", "file"),
]

# Layer 3：內容關鍵字（僅掃頂層這幾份 .md）
KEYWORDS = [
    "harness", "workflow", "agentic", "SDD", "BDD", "TDD", "subagent",
    "reviewer", "planning", "brainstorming", "unattended", "finish branch",
]
CONTENT_SCAN_FILES = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", "README.md", "ROADMAP.md"]
MAX_READ_BYTES = 64 * 1024

_CONFIDENCE_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}

_RECOMMENDATION_MAP = {
    "high": "use-detected-harness-as-main-flow",
    "medium": "ask-user",
    "low": "no-special-routing",
    "none": "no-special-routing",
}


def _path_matches(root: Path, rel: str, kind: str) -> bool:
    p = root / rel
    try:
        if kind == "dir":
            return p.is_dir()
        return p.is_file()
    except OSError:
        # 權限被拒 / 路徑異常等 → 視為未命中，維持 exit 0/2 契約，不讓例外冒出崩潰。
        return False


def _scan_layer1(root: Path) -> dict:
    """回傳 {"harnessmith": [命中路徑...], "superpowers": [命中路徑...]}。"""
    hits = {"harnessmith": [], "superpowers": []}
    for rel, kind in LAYER1_HARNESSMITH:
        if _path_matches(root, rel, kind):
            hits["harnessmith"].append(rel)
    for rel, kind in LAYER1_SUPERPOWERS:
        if _path_matches(root, rel, kind):
            hits["superpowers"].append(rel)
    return hits


def _scan_layer2(root: Path) -> list:
    return [rel for rel, kind in LAYER2_SIGNALS if _path_matches(root, rel, kind)]


def _keyword_pattern(keyword: str) -> re.Pattern:
    # split() 對單詞回傳單元素，對「finish branch」拆成多詞，一式同時涵蓋兩者。
    body = r"\s+".join(re.escape(part) for part in keyword.split())
    return re.compile(rf"\b{body}\b", re.IGNORECASE)


_KEYWORD_PATTERNS = [(kw, _keyword_pattern(kw)) for kw in KEYWORDS]


def _scan_layer3(root: Path) -> list:
    """只掃頂層指定 .md，各檔讀取上限 MAX_READ_BYTES，回傳命中證據字串清單。"""
    hits = []
    for fname in CONTENT_SCAN_FILES:
        p = root / fname
        try:
            if not p.is_file():
                continue
            # 只讀前 MAX_READ_BYTES：f.read(n) 只取 n bytes，不把整檔載入記憶體
            # （巨檔不會 OOM，才符合「讀取上限 64KB」的契約）。
            with p.open("rb") as f:
                raw = f.read(MAX_READ_BYTES)
        except OSError:
            continue
        text = raw.decode("utf-8", errors="ignore")
        for kw, pattern in _KEYWORD_PATTERNS:
            if pattern.search(text):
                hits.append(f"{kw} in {fname}")
    return hits


def detect(root: Path) -> dict:
    """對 root 執行三層只讀掃描，回傳符合 ROADMAP §4.1 schema 的 dict。"""
    layer1 = _scan_layer1(root)
    layer2_hits = _scan_layer2(root)
    layer3_hits = _scan_layer3(root)

    candidates = []
    if layer1["harnessmith"]:
        candidates.append({
            "name": "harnessmith",
            "confidence": "high",
            "evidence": layer1["harnessmith"],
        })
    if layer1["superpowers"]:
        candidates.append({
            "name": "superpowers",
            "confidence": "high",
            "evidence": layer1["superpowers"],
        })

    if not candidates:
        layer2_count = len(layer2_hits)
        layer3_count = len(layer3_hits)
        if layer2_count >= 2:
            candidates.append({
                "name": "generic-harness",
                "confidence": "medium",
                "evidence": layer2_hits,
            })
        elif layer2_count == 1:
            # 抗辯定案：單一 Layer 2 訊號一律 low，內容關鍵字不升 medium（見模組 docstring 計分規則註）。
            candidates.append({
                "name": "generic-harness",
                "confidence": "low",
                "evidence": layer2_hits,
            })
        elif layer3_count >= 1:
            candidates.append({
                "name": "unknown-workflow",
                "confidence": "low",
                "evidence": layer3_hits,
            })

    overall = "none"
    for c in candidates:
        if _CONFIDENCE_ORDER[c["confidence"]] > _CONFIDENCE_ORDER[overall]:
            overall = c["confidence"]

    return {
        "detected": overall != "none",
        "confidence": overall,
        "candidates": candidates,
        "recommendation": _RECOMMENDATION_MAP[overall],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="只讀 harness/workflow 偵測器（P0.5，見 ROADMAP.md §4.1）",
    )
    parser.add_argument("project_root", help="要偵測的專案根目錄路徑")
    args = parser.parse_args(argv)

    root = Path(args.project_root)
    if not root.exists() or not root.is_dir():
        print(f"錯誤：路徑不存在或不是目錄: {args.project_root}", file=sys.stderr)
        return 2

    result = detect(root)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
