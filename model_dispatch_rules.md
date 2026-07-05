# Model Dispatch Rules

一句話：主迴圈是指揮官——負責分析、派工、裁決；粗活與編碼派子代理，主迴圈只收結論、風險、決策。
模型選擇以 `CLAUDE.md` 分工表為準（唯一正本，此處不複製表內容以免雙源漂移；反方底線例外，正本見協議 §5 floor 句）；本檔規定「怎麼派」。

使用者 指示（2026-07-04）：非瑣碎的程式編寫與測試撰寫一律派 sonnet 執行；主迴圈（無論當前模型多強）負責分析與 workflow 派工。瑣碎單步（改一行、看一個檔）依下方例外由主迴圈直接做——「一律」不含瑣碎單步，兩條規則不衝突。

## Commander does not do bulk work

- 主對話在 Agent / Explore / Workflow 可用時，**不得**自己做大範圍 repo 掃描、批次讀檔、整目錄 grep。
- 觸發委派的機械判準（任一命中即派）：
  - 預估要 Read >10 個檔
  - Grep 結果 >100 行還需要逐檔深入
  - 任務形如「找出所有 X」「盤點整個 Y」→ 派 Explore（haiku）
  - 要寫或改程式碼/測試 → 派 sonnet（附派工包）
- 主對話收到的應是：結論 + 風險 + 建議決策 + 關鍵 file:line——不是原始檔傾倒。
- 例外：≤3 個已知路徑的精準讀取、改一行看一檔的瑣碎單步，主迴圈直接做（委派 overhead 反而更貴）。
- 正例：「找出所有呼叫 deploy() 的地方」→ 派 Explore，收回 file:line 清單 + 一句摘要。
- 反例：主迴圈自己 `Glob **/*` 然後 Read 30 個檔「以防萬一」——context 被灌爆，判斷品質下降。

## Dispatch packet

每次委派必含 7 欄，缺任一欄＝無效派工，子代理應先要求補齊而非開工：

```
目標 Goal：<一句話，可驗證，不是「幫我看看」>
範圍 Scope：<這次任務動什麼；一句話界定>
非目標 Non-goals：<明確不要做的事，至少 1 條（防順手改）>
允許路徑 Allowed paths：<可讀清單 + 可寫清單；寫入預設禁止，除非明列>
驗收標準 Acceptance criteria：<可機械判定，如「pytest tests/x.py 全綠」，不是「能動就好」>
回報格式 Report format：<指定下方模板>
停止條件 Stop conditions：<遇到什麼立刻停：範圍外檔案、編譯錯誤、機密、需要刪東西>
```

唯讀搜尋類輕量派工（如 Explore）：Non-goals / Allowed paths / Report format 三欄可填「預設」
（預設＝不寫入任何檔案／全 repo 唯讀／本檔回報模板），但欄位本身不可缺。

## Required report format

子代理回報一律用此模板（主迴圈收到缺段的回報，退回要求補齊）：

```
結果 TLDR：<一句話>
做了什麼：<動過的檔案清單，每檔一句>
證據：<測試命令 + 輸出摘要/量測值；沒有證據就寫「已修改、未驗證」，不得寫「應該可以」>
超出範圍發現：<看到但沒動的問題；只回報不修>
風險與未完成：<明列；真的沒有就寫「無，理由：…」，不得空白>
```

## Escalation and downgrade

- **一次實質錯誤即升級**（此門檻管「子代理交出的結果」；自己重試同一方法的門檻是 2 次，見 `cognitive_rubrics.md`）：子代理（sonnet/haiku）改錯檔、或驗收未過卻回報完成 → 該任務交回主迴圈（當前模型）接手分析，不給第二次盲試。
- **出界即停**：子代理動了 Scope 外的檔案 → 立即停止 → 先保全現狀（複製該檔到 .bak——壞狀態也是證據）→ 用 `git diff` 定位越界變更、只還原越界部分 → 回報「動了 X，已還原」。警告：整檔 `git checkout` 會把範圍內的未提交修改一起丟掉且不可復原，禁止當預設動作。
- **特殊語法檔鐵則**（PowerLanguage / EasyLanguage / Pine Script / SQL migration / CI YAML）：遇編譯或語法錯誤 → 收集完整錯誤訊息原文 → 升級回報，**嚴禁盲目重試**語法修補——每次盲試都在燒 token，且常越改越壞、動到不該動的區塊。
- **降級**：推理級任務中發現剩下的是機械性批次動作（改措辭、跑格式轉換）→ 拆出來派 haiku。

## Examples

**壞派工包**（缺 5 欄，子代理會自由發揮）：

> 「幫我看看 hooks 有沒有問題，順便修一修。」

**好派工包**（以本專案為例）：

> 目標 Goal：讓 tests/test_verify_gate.py 的 T9 案例通過（目前紅）。
> 範圍 Scope：只修 `.claude/hooks/verify_gate.py` 的 TEST_CMD_RE。
> 非目標 Non-goals：不重構其他函式、不改其他測試案例、不動註解。
> 允許路徑 Allowed paths：讀 tests/test_verify_gate.py + .claude/hooks/verify_gate.py；寫僅限 verify_gate.py。
> 驗收標準 Acceptance criteria：`python -m pytest tests/test_verify_gate.py -v` 全綠。
> 回報格式 Report format：本檔 Required report format 模板。
> 停止條件 Stop conditions：需要動 verify_gate.py 以外的檔案時停下回報；regex 改兩版仍紅時停下升級。

**壞回報**（無證據、無風險段）：

> 「都改好了，應該沒問題。」

**好回報**：

> 結果 TLDR：T9 已綠，全套 10/10 通過。
> 做了什麼：verify_gate.py 的 TEST_CMD_RE 加入 `deno test` 分支（第 31 行）。
> 證據：`python -m pytest tests/test_verify_gate.py -v` → 10 passed in 0.21s。
> 超出範圍發現：README 的 gate 說明少列 deno（未動）。
> 風險與未完成：regex 對「字串裡含 test 字樣的非測試命令」仍可能誤判，現有 T10 只覆蓋部分假放行樣式。
