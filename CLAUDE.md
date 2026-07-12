# Fable Protocol Kit — 專案指示

本專案是「讓 Opus/Sonnet/Haiku 以 Fable 5 的操作模式工作」的行為協議套件（hooks + skill + agents）。
行為協議本體由 SessionStart hook 注入（`.claude/hooks/fable_protocol.md`），此處只放模型分工、不可妥協守則、治理文件路由與專案守則。

## 模型分工（Model Routing）— 委派子代理時強制遵守

主迴圈無論當前是哪個模型，透過 Agent 工具或 Workflow `agent()` 委派時，依任務性質選 `model`：

| 任務性質 | model | 例子 |
|---|---|---|
| 邏輯推理、架構設計、根因分析、重大決策、抗辯裁決 | 當前模型（不指定 model） | 設計評估、bug 根因判定、judge panel |
| 程式編寫、重構、bug 修復、測試撰寫 | `sonnet` | 實作功能、改測試、修 lint |
| 檔案批次處理、文書編輯、資料搜尋、格式轉換、摘要 | `haiku` | Explore 搜碼、整理 log、改 README 措辭 |

- 瑣碎單步操作（改一行、看一個檔）主迴圈直接做，不委派。
- 抗辯三反方的 model 底線規則見協議 §5 與 adversarial-review skill（正本），此處不重複。
- 「當前模型」＝主迴圈直接做，或委派時省略 model 參數讓子代理繼承——推理力跟著 session 走，不降級到寫死的型號（指表格推理列；反方底線見協議 §5）。
- 改此表時必須同步改 `.claude/hooks/fable_protocol.md` §5（雙源同步）。
- 派工包 7 欄、回報模板、升級/降級規則見 `model_dispatch_rules.md`——委派時強制使用。

## 不可妥協守則（Non-negotiable Guardrails）

- **精準修改**：只動用戶要求的區塊；不順手重排、重格式化、刪無關程式碼。特殊語法檔（PowerLanguage / Pine Script / SQL migration / CI 配置）尤其嚴格。
- **註解與參數說明是受保護內容**：優化邏輯也不得刪參數說明、既有註解、交易假設、歷史備註；未經指示刪除＝失敗，不是清理。
- **先讀後寫、改前備份**：改任何既有檔案前必先 Read；必先建 `<檔名>.bak.<YYYYMMDD-HHMMSS>` 並確認存在——備份失敗即停。
- **工具誠實**：不得宣稱不存在的工具/檔案/權限；能力缺失就明說並降級（如輸出手貼內容）。
- **規則衝突時**：選更安全、更窄、可回復的動作；仍不確定 → 先問用戶再動檔案。

## 治理文件路由（Routing）

| 情境 | 讀這份 |
|---|---|
| 委派子代理（派工包 / 回報格式 / 升級降級） | `model_dispatch_rules.md` |
| 何時慢下來 / 問用戶 / 換路 / 升級模型；輸出前自我抗辯模組 | `cognitive_rubrics.md` |

## 專案守則

- 測試一律放 `tests/`，遵守全域 docstring 鐵則（四區塊 + 執行紀錄）。
- hooks 腳本改動後必須重跑 `python -m pytest tests/ -v` 且綠燈才算完成。
- `.claude/hooks/.last_*` 是 hook 觸發 marker（e2e 測試用），不要手動改、不要進版控。
- 佈署到全域（`C:\Users\user\.claude\`）前必須：本專案全部測試綠 + 用戶明確點頭。佈署步驟見 README.md。
- 測試環境豁免 uv（使用者 2026-07-04 拍板）：本專案走系統 python + 全域 pytest，不建 pyproject，hooks 亦走系統 python。
