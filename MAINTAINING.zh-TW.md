# 維護 Fable Harness

[English](MAINTAINING.md) &nbsp;·&nbsp; **繁體中文**

給本 repo 維護者的備註。使用這個 kit 不需要這份文件——那請看 [README](README.zh-TW.md) 與 [INSTALL.md](INSTALL.md)。

## 讓貢獻者名單保持乾淨（不長 `noreply` / Claude phantom）

Claude Code 預設會在它協助寫的 commit 尾端附上一行 `Co-Authored-By: Claude <noreply@anthropic.com>`。GitHub 會把這行 trailer 當成一位貢獻者，於是 repo 的 **Contributors** 側欄會冒出一個不是真人的 `noreply` / `claude` 項目。兩層防線把它擋掉。

### 1. 你自己的 commit——已自動處理

`.claude/settings.json` 設定：

```json
"attribution": { "commit": "", "pr": "" }
```

這告訴 Claude Code：在本 repo 建立的 commit 與 PR 不要附加 co-author trailer（或 PR 頁尾），所以你自己的 commit 不會生 phantom。每次 commit 都不用特別處理。

### 2. 貢獻者的 PR——合併 SOP

你無法控制貢獻者用的設定，所以他們的 PR commit 可能仍帶著 Claude trailer。在**合併時**把它拿掉。

**收 PR 一律用「Squash and merge」（壓縮合併）**——這是唯一能讓你編輯最終 commit 訊息的合併方式。

1. 在 PR 頁，點合併鈕的下拉箭頭，選 **Squash and merge**。
2. 在可編輯的訊息框裡，**刪掉 email 為 `noreply@anthropic.com` 的那一行**，例如：
   ```
   Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
   ```
   顯示名稱可能是 `Claude Opus …` 或 `Claude Fable 5`——認 `noreply@anthropic.com` 這個位址，別認名字。
3. 若有**真人**的 `Co-authored-by:` 行（例如 `... <某人@users.noreply.github.com>`），**要保留**——那是真正的協作者，應該被記功。
4. 確認壓縮合併。

真人 PR 作者仍會被記功——他是 commit 的**作者（author）**，與任何 co-author 行無關。被拿掉的只有 Claude phantom。

CLI 等效指令：

```
gh pr merge <PR> --squash --body "<不含 Claude 那行的乾淨訊息>"
```

### 為什麼不用其他合併方式

**Create a merge commit** 與 **Rebase and merge** 會原封不動照搬 PR 的原始 commit，Claude trailer 因此存活、phantom 又出現。只有 **Squash and merge** 能讓你編輯訊息。

### 這套做法「不會」做到的事

- **不溯及既往。** 已經合併進去的 commit 仍帶著它當初的 trailer。要清那些得改寫已發佈的歷史，而我們刻意不做——那會弄壞開啟中的 PR 與 forks。
- **不要**為了避開 trailer 就把一個好的 PR 關掉、自己重寫。那等於抹掉一位真實貢獻者。請照收、合併，然後只刪那一行。
