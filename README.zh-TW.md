# Fable Harness

> 一套隨插即用的行為協議，讓 Claude Code（Opus / Sonnet / Haiku）像個有紀律的工程師一樣工作——動手前先查證、把假設講清楚、重大結論先找人挑戰過再採信、用真正的測試證明改動有效。

[English](README.md) &nbsp;·&nbsp; **繁體中文** &nbsp;·&nbsp; [简体中文](README.zh-CN.md) &nbsp;·&nbsp; [日本語](README.ja.md) &nbsp;·&nbsp; [한국어](README.ko.md)

![Version: 1.0.0](https://img.shields.io/badge/version-1.0.0-blue.svg) &nbsp; ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## 這是什麼

Fable Harness 是一個小型套件——幾個 hooks、一個 skill、幾個子代理——會在每次開啟 Claude Code session 時自動注入。它不會教 Claude 新招式，而是確保 Claude **每一次都照著一套有紀律的流程走**：先蒐集證據再回答、把假設講出來而不是用猜的、對自己的重大結論先自我挑戰，並且拿出真正的證據（而不是「看起來沒問題」）證明改動真的有效。

可以把它想成是「行為的底線」，不是完整的開發框架。它不會幫你排 sprint、不會幫你跑 CI 流程——它做的是在 agent 工作的過程中，讓它保持誠實、謹慎、可驗證。

## 為什麼會有這個 kit

本專案蒸餾自第二次的 Fable 開放版本（Anthropic 的 Fable 模型）——那種謹慎、有紀律的做事方式。與其把這份紀律鎖在單一模型裡，這個 kit 把它提煉成一套可重複使用的協議，用來強化 Opus（以及其他 Claude 模型）身邊的工作架構，讓不管是哪個模型在主導，都能維持同一套紀律。

誠實說在前面：hooks 和 skill 只能移植「程序」本身（先蒐證、講假設、交叉質疑結論、要求驗證證據），沒辦法移植一個模型天生的判斷力。但實務上，「表現得好」跟「表現得隨便」之間的落差，大多來自程序被跳過，而不是判斷力不足。這正是這個 kit 想補上的落差。

## 運作機制

- **OODA 迴圈**——回答前，Claude 先蒐集證據（實際搜尋/讀取檔案，不靠訓練記憶亂猜），把假設講出來，把任務轉成一個可驗證的目標（「讓它能動」這種說法不夠），然後小步修改、每一步都驗證。
- **多方抗辯（adversarial review）**——這個 kit 最具特色的機制。在採信一個重大結論之前（架構決策、根因判定、任何可能影響上線環境的結論），Claude 會**同時**派出三個獨立的「反方」子代理，各自負責不同角度：**skeptic** 專找邏輯漏洞、**red-team** 專找安全與失效風險、**simplifier** 專找不必要的過度工程。三個鏡頭裡要過半「存活」（沒被推翻），結論才算採信。
- **模型分工**——推理、架構設計、根因分析留給當下主導的模型；寫程式與重構交給 Sonnet；批次檔案處理、搜尋、文字整理交給 Haiku。用剛好合適的模型做剛好合適的事。
- **完成定義（Definition of Done，TDD）**——只要改到實際邏輯，就要有自動化測試，並且證明「改之前測試會失敗、改之後測試會通過」。單純看輸出順不順眼，或隨手一個 `console.log`，都不算驗證。
- **誠實回報**——任何回報的第一句話就是實際結果（不是鋪陳），失敗就照實講，不美化。

## 裡面有什麼

| 元件 | 檔案 | 作用 |
|---|---|---|
| 行為協議 | `.claude/hooks/fable_protocol.md` + `inject_protocol.sh` | 每次 session 開始時注入 |
| 每輪微提醒 | `.claude/hooks/prompt_nudge.sh` | 使用者每則訊息都會被注入一行提醒 |
| 驗證關卡 | `.claude/hooks/verify_gate.py` | 若這輪改了程式碼卻沒跑測試，擋下收工一次（第二次會放行） |
| 多方抗辯 | `.claude/skills/adversarial-review/` | 定義上述三反方審查流程的 skill |
| 反方子代理 | `.claude/agents/{skeptic,red-team,simplifier}.md` | 抗辯流程用的三個獨立子代理角色 |
| 模型分工 | `CLAUDE.md` | 上面提到的分工表 |
| harness 偵測器 | `scripts/detect_harness.py` | 只讀檢查——這個專案是不是已經有自己的開發 harness（例如 harnessmith、Superpowers），有的話 Fable 就退居底線角色 |
| 治理文件 | `diagnostics.md`、`model_dispatch_rules.md`、`cognitive_rubrics.md`、`future_session_letter.md` | 已知失效模式、子代理派工範本、何時該慢下來的判斷準則、跨 session 交接紀錄 |

## 快速開始

把這個 repo clone 下來，然後跟你的 Claude Code 說：**「照 INSTALL.md 安裝 Fable Harness。」** Claude 會自己讀說明並安全地完成安裝（先備份、絕不覆蓋你既有的設定）。詳細會做什麼請看 [INSTALL.md](INSTALL.md)。

## 版本規則

本 kit 採用[語意化版本（Semantic Versioning）](https://semver.org/lang/zh-TW/)——`主版本.次版本.修訂號`，自 **1.0.0** 起：

- **主版本（MAJOR）**——協議契約的破壞性改動（移除或改名 hook／skill／agent，或改變協議注入方式、子代理派工方式且不相容），使用者需重裝或調整設定。
- **次版本（MINOR）**——向後相容的新增（新的 hook、skill、agent 或治理規則），既有安裝可照常運作。
- **修訂號（PATCH）**——向後相容的修正或措辭調整（hook 修 bug、規則講清楚、錯字）。

目前版本記在 [VERSION](VERSION)；重要變更記於 [CHANGELOG.md](CHANGELOG.md)。

## 授權

MIT — 詳見 [LICENSE](LICENSE)（翻譯版：[繁體中文](LICENSE.zh-TW)）。
