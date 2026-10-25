# Changelog

All notable changes to Fable Harness are recorded here.

This kit follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`:

- **MAJOR** — a breaking change to the protocol contract (a hook/skill/agent removed or renamed, or an incompatible change to how the protocol is injected or how agents are dispatched) that would require users to re-install or change their setup.
- **MINOR** — a backward-compatible addition (a new hook, skill, agent, or governance rule) that existing installs keep working alongside.
- **PATCH** — a backward-compatible fix or wording change (a bug fix in a hook, a clarified rule, a typo).

The current version is also kept in [VERSION](VERSION).

## [Unreleased]

## [1.8.0] — 2026-10-26

### Fixed

- **目標關卡把測試指令本身的機密寫進本機狀態檔**：`.fable/goal_state.json` 的 `red`／`red_seen`
  以指令文字當鍵，`pytest --api-key=X` 的 X 以明碼落地。現在鍵是雜湊組合
  （context、指令段、剝掉輸出格式旗標的指令段各一段 sha256），`red`／`red_seen` 的鍵不含指令原文。

### Changed

- **context 的值不同就是不同目標**：`TOKEN=a pytest t.py` 與 `TOKEN=b pytest t.py` 以前因為值被遮成
  `***` 而同鍵、一條的綠會解掉另一條的紅；現在異鍵。黏著分隔符的寫法也因此分開，例子見已知限制表。
- **指令裡字面的 ` :: ` 不再被切成 context**（以前 `pytest -k "a :: b"` 的 `pytest -k "a` 會被當成 context）。
- **舊版狀態檔的鍵在下一次正常跑完的 Stop 時丟棄**：1.7.0 及更早的文字鍵算不回新身分，次數不遷移，
  那些目標的階梯從 1 重算。

### Known limitations

- **低熵機密可被猜**：雜湊吃未遮的值，持有狀態檔的人可以逐一猜測短密碼並比對。
- **同一份狀態檔不可由新舊兩版 hook 處理**：兩版同時處理同一個 Stop 時，兩道階梯都可能無聲失效
  （連紅不擋、不擱置）；而且舊版每處理一次 Stop 就重寫一次帶明碼的文字鍵，混用期間上面 Fixed 那條
  不成立。新版要到下一次正常跑完的 Stop 存檔才丟掉這些鍵，只讀的入口（使用者送出訊息時的注入）與
  閘自己走 fail-open 的那次 Stop 都不清。全域與專案的 hook 必須指向同一版。
- **降回 1.7.0 再升回時計數可能失真**：降版期間 1.7.0 的綠收不掉新版留下的紅，在該目標最後一次
  紅的 24 小時內升回，那些目標可能直接被擋或擱置；降版期間 1.7.0 的權威驗證綠會清掉新版所有的紅，
  不分 context。
- **擱置紀錄與擋下訊息沿用原本的遮蔽**：1.6.0 列出的半遮形狀照舊會進擱置紀錄並注入對話。
- **context 是字面擷取結果**（1.6.0 起的限制，現行行為如下）：

  <!-- G113:context -->
  | 指令 A | 指令 B | A 的 context | B 的 context | 鍵 |
  |---|---|---|---|---|
  | `A='x'y pytest t.py` | `A='x'z pytest t.py` | `A=x` | `A=x` | `同鍵` |
  | `cd "$HOME"/projA && pytest t.py` | `cd "$HOME"/projB && pytest t.py` | `cd=$HOME` | `cd=$HOME` | `同鍵` |
  | `cd a; pytest t.py` | `cd a && pytest t.py` | `cd=a;` | `cd=a` | `不同鍵` |
  | `TOKEN=a pytest t.py` | `TOKEN=b pytest t.py` | `TOKEN=a` | `TOKEN=b` | `不同鍵` |
  | `TOKEN=abc&&pytest t.py` | `TOKEN=abc && pytest t.py` | `TOKEN=abc&&` | `TOKEN=abc` | `不同鍵` |
  <!-- /G113:context -->
- **一次呼叫串好幾條測試時，結果可能算到錯的目標，誤清與誤擋都會發生**：目標從第一個測試指令起擷取，
  剝掉引號外 `|`、`>` 起的尾段；成敗取輸出裡最後一行「N passed／failed／errors」。所以
  `pytest a.py | tail -3; pytest b.py | tail -3` 這類寫法，b 的結果算在 a 頭上：b 綠時可能解掉 a 的紅
  （a 是權威驗證指令時，解掉同 context 所有紅）；b 紅時 a 被記一次失敗，可能因此被擋或擱置。
- **`--tb=`、`--color=` 的值緊貼分隔符時，兩條指令可能被當成同一個目標**：`pytest a.py --tb=no;pytest -k slow b.py`
  與 `pytest a.py -k slow b.py` 被視為同一個目標，一條的綠可能解掉另一條的紅。分隔符前留空白可避免。
- **接線閘對 `git -C <路徑>` 的路徑照字面使用**：Git Bash 寫法（`/c/Users/...`）、`~`、未展開的 `"$VAR"`
  在 Windows 上可能找不到 repo，那一次 commit 不做接線檢查，`--no-verify` 也放行。
- **任一 Stop hook 擋下之後，目標閘不讀接下來的測試結果（待修）**：Claude 因 Stop hook 擋下而繼續工作時，
  帶 `stop_hook_active` 的 Stop 目標閘直接放行、不讀測試結果；回合若在這種 Stop 結束、下一個回合又由使用者
  輸入開始，這些結果之後就讀不到（由背景通知開始的回合仍會讀到）。所以這期間的紅可能不累加，該擋時可能沒擋、
  該擱置時可能沒擱置；這期間的綠也可能解不掉紅，下一個回合同一目標再紅時可能被誤擋或誤擱置。1.5.0 起即有。

## [1.7.0] — 2026-10-24

### Changed

- **模型分工表改寫**：haiku 列改為判準「結果能直接檢查對錯的純蒐集與粗活」加例子，
  刪「文書編輯」「摘要」；「資料搜尋」拆成 repo 內搜碼（haiku）與上網查資料（sonnet）；
  翻譯與需要判斷一致性的比對（跨檔反向引用、數字對帳）歸 sonnet；主迴圈列補規劃、統籌、
  驗收子代理交回的 diff。CLAUDE.md、協議 §5、model-dispatch-rules skill、五語 README 同批改。

## [1.6.0] — 2026-10-18

### Fixed

- **目標關卡把同一次紅重複計數**：每次 Stop 都重讀整個回合，同一次紅的執行每次
  Stop 都再加 1；自主長跑時一個回合會 Stop 很多次，一次紅就被計成 3～4 次而擱置。
  改為以工具呼叫 id 去重複：計數單位是 Stop 劃界的工作段落，段落結束時仍紅才記一次，
  同一筆紅結果不會在之後的 Stop 被重算（協議 §4b-1 第 7 條）；權威驗證綠收束時
  綠之前的紅也記成已計（逐 context 判定，多個 context 各自收束；未收束 context 的紅照常計數，
  不再被權威綠的提早結束吞掉）；已計清單有保留上限（512 筆），
  只裁掉舊 id；目前回合裡每個目標最後一筆結果的 id 不受此限。
- **只差輸出格式旗標就被當成兩個目標**：`--tb=no` 的紅與 `--tb=short -rf` 的綠
  解不開。紅綠解除時改剝掉只改輸出長相的 pytest 旗標，解除順序依 §4b-1 第 3 條（已記過的紅之後出現過綠才解，綠在紅之前不解）
  （§4b-1 第 5 條；是不是 pytest 看鍵的第一個 token——鍵已從測試工具本身起算，參數位置的
  `pytest` 不算；不分大小寫，引號包住的旗標（含 `"-p" "no:cacheprovider"`）也剝，`-r` 只認報告字元）；計數仍逐鍵，狀態檔與
  擱置紀錄裡的鍵仍是實際下的指令。
- **已記過的紅之後出現綠，紅就收束**：段落只看最後一筆時，「紅→綠→紅」中間的綠被後面的紅
  蓋掉，測試先行每片一紅一綠也會在第三片被擱置。現在已計的紅之後只要出現同一目標的綠，
  那個紅就收束，之後的新紅從 1 計（§4b-1 第 3 條）；權威驗證綠同理（同一 context 內）。
- **權威驗證指令只差輸出格式旗標就比對不到**：宣告 `python -m pytest tests/ -q`，實跑帶
  `-p no:cacheprovider` 或 `-rf --tb=no` 時宣告形同無效。比對兩邊都先剝格式旗標；選取旗標不同仍不相符。

### Known limitations

- **鍵以第一個 `pytest` 子字串定起點**：`uv run --with pytest==8 pytest …` 這類寫法，`pytest==8`
  會成為 runner 位置而判不出是 pytest，格式旗標不被剝——結果是紅燈不被解掉（保守方向），
  不會誤解紅燈。`-vvv`、`--quiet`、`--verbose`、合併短旗標（`-qx`）、`--tb no`、大寫的 `-Q`／`-V`
  也都不剝，同屬保守方向。
- **綠只出現在別的 transcript 時看不到**：子代理（worker）在自己的對話裡把測試轉綠，主對話的閘門
  看不到那個綠；主對話只跑紅的話，測試先行的每一片仍會被算成連敗。規避：子代理回報轉綠後，
  主對話用同一條測試指令（選取相同、輸出旗標可不同）親自跑一次綠。
- **計數單位是 Stop 劃界的段落**：同一段落內同鍵真的連紅三次（中間有改碼）也只計 1——假陰性，
  保守方向（寧可少擋，不誤擋）。
- **引號字串裡出現「pytest」仍會被當成測試指令**：例如交給其他工具的長提示文字含「pytest」字樣。
  鍵從那個字樣起算，紅綠都對不上真正的目標；與 heredoc 內文同一類，尚未處理。
- **heredoc 內文含 `pytest` 字樣會被當成測試執行**：鍵從內文裡的字樣起算，那筆執行的紅綠都對不上真正的目標。
- **「不是真的執行」的判斷看整條指令**：heredoc 內文含 `--collect-only`／`--version` 等字樣時，
  後面真跑的 pytest 整筆不記（紅綠都看不見）——假陰性。
- **context 是字面擷取結果，不是實際 shell 環境**：本版沿用 v1.5.0 的
  context 擷取與機密遮蔽行為。目標閘以固定正規表示式擷取測試指令前段的
  `cd` 與 `名稱=值`，再做字串整理與遮蔽；不解析 shell，也不保證辨識實際的
  工作目錄、環境變數或作用域。合法寫法也可能漏認、截斷，或把參數文字誤算
  進 context。前段從第一個字面 `<<` 起全部不參與 context 擷取，包括其後
  真正執行的 `cd` 與賦值；不判斷該記號是否真的是 heredoc。

  不同目錄或環境可能被合併成同一個目標，讓一邊的綠解除另一邊的紅，或混算
  失敗次數；同一目標也可能因字面寫法不同而拆成不同鍵，造成綠解不掉舊紅，
  或連紅分散、達不到阻擋門檻。權威驗證的「同一 context」也受此限制，
  不能視為實際環境相同的保證。

  以下是代表例，不是完整支援清單；表中 context 不含測試指令本身：

  | 指令 A | 指令 B | A 的 context | B 的 context | 鍵 |
  |---|---|---|---|---|
  | `A='x'y pytest t.py` | `A='x'z pytest t.py` | `A=x` | `A=x` | `同鍵` |
  | `cd "$HOME"/projA && pytest t.py` | `cd "$HOME"/projB && pytest t.py` | `cd=$HOME` | `cd=$HOME` | `同鍵` |
  | `cd a; pytest t.py` | `cd a && pytest t.py` | `cd=a;` | `cd=a` | `不同鍵` |
  | `TOKEN=a pytest t.py` | `TOKEN=b pytest t.py` | `TOKEN=***` | `TOKEN=***` | `同鍵` |

  精確行為以 `.claude/hooks/goal_gate.py` 的 `test_key`、`CD_RE`、
  `ENV_PREFIX_RE`、`run_context` 與 `redact` 為準。

- **機密遮蔽不完整**：context 中被機密名稱規則命中的值會遮成 `***`，
  因此不同機密值可能不再區分；名稱未被規則辨識的機密不保證遮蔽。
  測試指令本身（旗標、位置參數等）不經遮蔽，其中的機密會以明碼保留在本機
  `.fable/goal_state.json` 的 `red`／`red_seen` 鍵中。
  擱置紀錄與擋下訊息雖會經過遮蔽，仍可能殘留機密並進入對話，例如：

  <!-- G113:redact -->
  | 輸入 | 遮蔽後 |
  |---|---|
  | `TOKEN=a"b c" pytest t.py` | `TOKEN=*** c" pytest t.py` |
  | `pytest t.py --api-key=a"b c"` | `pytest t.py --api-key=*** c"` |
  <!-- /G113:redact -->

  不應把出現 `***` 視為整段機密已清除的保證。
  閘只在 `.fable/.gitignore` 不存在時建立忽略規則；既有設定與已追蹤檔案
  不保證受到保護，不能一概宣稱這些資料不會進入版本控制。

- **狀態檔的 `streak` 欄可能失真**：任一 context 被權威驗證的綠收束、另一個目標轉綠、或某一項被擱置時，
  `.fable/goal_state.json` 的 `streak` 會歸零，即使其他鍵仍有已計紅；另一個鍵出現新紅時，它也會被改寫成那個鍵的次數；擋下訊息與擱置清單用各鍵自己的次數，
  實際計數與是否阻擋不受影響。

### Changed

- **pre-commit 改為薄殼**：各 repo 的 pre-commit 不再是 `wiring_runner.sh` 的複本，而是一支薄殼
  （`.claude/hooks/precommit_shell.sh`），每次 commit 讀 Fable `main` 上已 commit 的 runner 並執行，
  commit 進 Fable `main` 即是部署，未 commit 的工作樹改動不會生效。runner 跑完必須回報「至少跑過一條守衛」，
  沒有回報（例如 runner 被改成什麼都不做）時薄殼擋下 commit，`ALLOW_UNWIRED=1` 仍可明示放行；
  因此 Fable `main` 不可退回 1.6.0 之前的 runner——舊 runner 不回報，所有裝了薄殼的 repo 都會被擋。新增安裝腳本
  `scripts/install_precommit.sh <Fable 路徑>`：只取代本 kit 自己的舊 hook（先備份），遇到非本 kit 的
  hook、`core.hooksPath`、非 git clone 的 Fable、含 `"` `$` 反引號的路徑一律拒絕且不寫檔。
  INSTALL.md 步驟 10、接線閘擋下訊息與 session 開場提示都改指向安裝腳本。
  **從 1.5.0 升級**：先前已 opt-in 的 repo 仍是舊的 runner 複本，更新 Fable clone 不會換掉它；每個這樣的 repo 要重跑一次安裝腳本
  （舊複本會備份），自己整合過的 hook 要照 INSTALL 步驟 10 重新整合。
- **反方唯讀**：skeptic 與 red-team 不再修改任何檔案；需要改檔才能證明的反例，
  改為寫出重現步驟並標為未驗證，交回主迴圈驗證。

## [1.5.0] — 2026-09-07

### Added

- **目標關卡逐鍵計數**：每個測試目標各自累加失敗次數，不同目標互不影響。協議
  新增 §4b-1，把「同一個目標」定義到可實作（身分＝測試指令的鍵）。
- **`.claude/fable-verifier`**：repo 可以宣告一條權威驗證指令；它變綠就收束所有
  尚未轉綠的失敗鍵。權威綠必須出現在紅之後才算數。
- **`scripts/release.py`**：發佈前置條件檢查——工作區乾淨、`VERSION` 相符、
  `CHANGELOG.md` 有該版章節、測試全綠、**這個 commit** 有抗辯審查紀錄，任一不過
  即拒絕。`--attest` 記錄審查並綁 commit hash；`--override-review --reason "…"`
  是留痕的緊急出口，會在發佈說明標上 `ADVERSARIAL_REVIEW_BYPASSED`。
- **屍檢遙測 `note_quiet()`**：三道閘的每一次 fail-open 寫一行到
  `.claude/hooks/.gate_fail`（時間戳、呼叫點標籤、例外類別；結構上不寫 payload），
  同一標籤上限 20 行。
- **SessionStart 會讀 `.gate_fail`**：注入總筆數與最近 5 行，只印符合自身格式的行。
- **接線閘認得 git 的四條 transient config 通道**：`-c`、
  `GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n`、`--config-env=`、`GIT_CONFIG_PARAMETERS`。
  指令裡出現 `hooksPath` 而閘解析不出來時一律擋（fail-closed）。
- **接線閘認得包裝過的 commit**：包裝器由 9 種擴到 17 種，新增 `timeout`、
  `winpty`、`setsid`、`unbuffer`、`chronic`、`ionice`、`strace`、`busybox`。
- **接線閘逐一判定一列裡的每個 `git commit`**，不再只看第一個。
- **`tests/test_no_silent_gate.py`**：AST 掃描，任何會吞掉失敗的地方必須留痕，
  或在原始碼標 `# quiet-ok: 理由`。檔案清單掃目錄，不寫死。
- **`tests/test_wiring_oracle.py`**：行為預言機，真的執行生成的指令，用
  「commit 有沒有成立、守衛有沒有跑」當真相，而不是斷言在判定函式上。

### Changed

- 目標關卡**維持硬擋，不降級為勸告**；精準度由 §4b-1 的定義負責。
- 判不出成敗的測試輸出改判 `vacuous`：既不累加失敗、也不解除既有失敗。原本判為
  通過，而通過會清掉整條階梯。
- 失敗鍵有 24 小時保鮮期，過期自動淘汰；淘汰上限只作用在過期的鍵上。
- `.gate_fail` 改用 `os.open` ＋單次 `os.write`（含 `O_BINARY`），並鎖獨立的
  `.gate_fail.lock`；文字模式 append 在 Windows 上會掉筆。
- 測試一律驅動閘的副本，不再寫進產品自己的遙測檔。

### Fixed

- 提示檔的檔名改問 `git rev-parse --git-path`，不同 repo 不再撞同一個檔名。
- 兩個 session 同時擱置不再遺失一筆（狀態的讀改寫加了鎖檔）。
- `.fable/.gitignore` 一定會被寫出來；三處會建該目錄的寫入者改用同一條判準。
- `go test`／`dotnet test`／`mvn`／`phpunit` 的失敗不再被判成通過。
- 機密遮罩補上 `$env:TOKEN = "…"`（PowerShell 慣用寫法）與 `mysql -pPASS`。
- `.claude/fable-verifier` 含非 UTF-8 位元組時不再讓整道閘靜默失效。
- 手改狀態檔造成型別錯誤時，不再靜默刪掉使用者寫的擱置備註。
- `git commit -m"訊息"`（`-m` 後不接空白）不再被誤擋，訊息內文仍會被剝掉。
- `.fable` 是一般檔案時，Stop 不再每次固定停 1.5 秒。
- `release.py --check` 乾跑不再留下審查紀錄；緊急出口的痕跡不再被下一次發佈
  當成合格審查。

### Known limitations

- **指令樣式有兩處指數級回溯，本版新增。** 前綴層：`sudo -u ci env PATH=/x nice
  -n 10 timeout 60 ` 連續重複 4 次（193 字元）要 6.63 秒；git 全域選項層：
  `git ` 後接 `--git-dir --foo ` ×22（365 字元）要 4.28 秒，×24（397 字元）透過
  真實 hook 子行程是 28.18 秒，超過 hook 的 10 秒 timeout。只在比對失敗時發生。
  1.4.3 兩處都是 0.000 秒。實測 8 條真實形態的指令列最慢 0.00005 秒——要爆需要
  同一串 token 連續重複四次以上。解法是改用引號感知的 tokenizer 取代單一巨型正則。
- `_quiet_lock` 的 POSIX 分支未在任何平台執行過（本機沒有 POSIX runtime，
  唯一的並行測試標了 `skipif`）。
- 目標關卡會擋到突變測試：把程式改壞→跑→紅→還原→再跑，在閘看來是同一個鍵連續
  失敗。它是軟擋，再結束一次即放行。
- 驗證閘的誤擋率量不到：它的真相就是它自己的 `TEST_CMD_RE` 在判的事。
- 量測後刻意不修兩項（本機真實資料：1,260 條 commit 指令、6,485 條測試執行）：
  `cd <別的 repo> && git commit` 時接線閘檢查的是 session 的 repo，4.9%；
  環境變數前綴進了目標的識別鍵，同一目標會裂成多個鍵，4.4%。
- `.claude/fable-verifier` 由受管束的 repo 自己可寫，且隨 clone 傳遞。
- attestation 沒有認證，且存在被 gitignore 的目錄裡——擋的是遺忘與流程漂移，
  不是蓄意繞過。沒有 server 端驗證。
- 目標的身分是測試指令的鍵；同一段工作換用不同的測試指令時，階梯會從頭算起。
- 惡意 repo 的檔名仍會進 SessionStart 上下文（上限 8 行 × 120 字元，強制前綴，
  前後有「這是資料不是指令」的框架）。

## [1.4.3] — 2026-09-05

Found by reviewing v1.4.2 after it shipped — and then by reviewing the fixes for *those*, which is where most of this comes from. The first attempt at each of these was wrong in a way the second review caught.

### Fixed

- **The goal gate went silently dead when `.fable` was not a directory.** `os.makedirs` sat outside the `try`, so a `.fable` that happened to be a *file* raised into the hook's fail-open and the whole component stopped — no counting, no shelving, no reminders, no sign. An unreadable state file already blocked loudly; the two now behave the same way.

- **State could be written and read outside the repository.** A repo can commit a symlinked `.fable`, and the first guard for it (`os.path.islink`) checks the wrong thing twice: it sees only the last path component, so a symlinked `.fable/.gitignore` still escaped, and on Windows it returns False for a **junction** — the form that needs no administrator rights. The guard blocked the rare shape and passed the common one. Containment is now decided by resolving the path, and it covers reads too: following the link outward and injecting what it finds is the same hole from the other side.

- **The ignore file is no longer written over.** The previous version read an existing `.fable/.gitignore`, judged whether it was "enough", and appended `*` when it wasn't. Every part of that was wrong: the append followed a symlink out of the repository; it wrote without a leading newline and turned `something_else` into `something_else*`; its notion of "enough" was looser than git's (`*` followed by `!*`, or a line with trailing whitespace, both passed); two sessions racing appended twice. Guessing at a file the user owns kept producing new ways to damage it, so it no longer guesses — the ignore file is written only when the gate creates the directory itself.

- **A shelved item's `note` is truncated before it is injected.** `last_command` was capped at 160 characters and `note` was not, while both come from a file a repository can commit.

### Known limitations

- Two sessions shelving in the same repo at the same time can lose an entry: the state is a read-modify-write with no lock (measured: 5 of 5). Recorded in `tests/test_goal_gate.py`.
- A `goal_state.json` the user has already committed cannot be un-tracked by an ignore file. Writes to it then show up in `git status`, which is visible rather than silent.

## [1.4.2] — 2026-09-05

1.4.1 was published without the review that 1.4.0 had just made mandatory. Running it afterwards found that 1.4.1 had fixed one instance of a class and left the class alive — plus two regressions of its own.

### Fixed

- **The whole gate was off in any repository whose path contains non-ASCII characters, on the platform this kit targets.** `subprocess.run(..., text=True)` decodes git's UTF-8 output with the *locale* encoding; on a factory zh-TW / ja / ko Windows (`PYTHONUTF8=0`, cp950) that raises inside subprocess's reader thread, `stdout` comes back `None`, `.strip()` raises `AttributeError`, and the hook's fail-open swallows it. Measured: `git commit --no-verify` in an opted-in repo under a Chinese path was **not blocked**, and a traceback went to stderr. All four subprocess calls in the two hooks now decode as UTF-8 explicitly.

  1.4.1 changed how the *file name* was computed and never touched the decode boundary one layer earlier — the same class, one step up. The test that guarded 1.4.1's fix inherited the author's `PYTHONUTF8=1`, so it proved the author's environment rather than the fix; it now runs with the platform default.

- **`cut -c1-120` truncates bytes, not characters** (GNU coreutils), so a CJK file name could be cut mid-character and put a broken UTF-8 sequence into the session context. The fix for "bytes versus characters" had committed the same error one line later. Truncation moved to the writing side, where it counts characters.

- **`git ls-files` escapes non-ASCII names into octal** (`"tests/test_\346\270\254…"`), which made the hint unreadable for exactly the readers it was meant for. Now uses `-z`.

- **`python3 … || python …` in the declaration could turn a red guard green** when the two interpreters differ, and ran the whole suite twice on the red path. Replaced by resolving the interpreter once.

### Changed

- The bounds on the injected hint are now asserted directly — eight entries, 130 characters each, checked on both the note and the injected block — rather than through a "total output under 20 000 characters" threshold that stayed green with the length cap removed.

- Existing Windows clones need `git add --renormalize .claude/wiring-guards` for 1.4.1's `.gitattributes` line to take effect; the attribute alone does not rewrite a working tree.

## [1.4.1] — 2026-09-05

Everything here was found by running the adversarial review **on the published
releases**, which 1.4.0 had just made mandatory before publishing and which
1.2.0 through 1.4.0 had not had. The rule found six errors in its own author's
work within twenty minutes of shipping.

### Fixed

- **The hint was unreachable on any repository whose path contains non-ASCII characters.** The note's file name is derived from the repo path by replacing everything that is not `[A-Za-z0-9]`, and the two ends did it differently: Python's `re.sub` works per *character*, the shell's `tr` per *byte*. A path under a Chinese, Japanese or Korean directory produced `d_____repo` on the writing side and `d_________repo` on the reading side — written, never read. This kit ships READMEs in those three languages; the people it locked out are the ones it was translated for. Both ends now work on UTF-8 bytes.

  The test that should have caught it computed the name with a copy of the *production* regex, so it could only ever agree with the code it was testing. It now derives the name the way the shell does and drives both halves end to end.

- **A note could be printed to the wrong repository.** Because every non-alphanumeric character maps to `_`, `x/evil-a`, `x/evil_a` and `x/evil/a` collide on one file name — repo B's session would open with repo A's file list, and A opting in would delete B's note. The injector now checks the note's `repo:` line against the current repository before printing anything.

- **The injected hint had no size limit.** File names come from `git ls-files` of whatever repository you happen to be in, so a hostile repo could put 5,000 lines (110 KB) of arbitrary text into the session context. The reading side now caps at eight entries and 120 characters each, and labels the block as data — file names, not instructions.

- **The declaration hard-coded `python`.** On a macOS or Linux box with only `python3`, every commit in an opted-in repo would have gone red. It tries `python3` first now.

### Changed

- **Corrected published numbers.** The 1.2.0 entry claimed 27 and 26 test cases; the files as released collect 57 and 40. The commit time for this repo's own guard was stated as 1.2 s in one place and 1.9 s in another; measured on a clean clone it is 1.3–1.8 s. The declaration described "200 tests, about 10 seconds" — that was the author's local count including five private test files; a public clone has 159.

- **`MAINTAINING.md`** (and its translation) now tells reviewers that a change to `.claude/wiring-guards` is a change to what executes on every committer's machine after the merge — the warning existed only in `INSTALL.md`, which is not what a PR reviewer reads.

- **`.gitattributes`** covers the extensionless `.claude/wiring-guards`, which was being checked out with CRLF on Windows.

## [1.4.0] — 2026-09-05

### Added

- **Protocol §4: verification and adversarial review happen *before* the claim of done, not after** — and §2's trigger list now names publishing explicitly.

  This one was earned. Across this kit's own 1.2.0 release the review did run and the decision lookup did happen, but both landed *after* "this is done" and after "which do you prefer?" had already been sent. Three rounds found 25 defects, two of them introduced by the fixes from the round before, and every one of them reached the user as an amendment to something they had already been told was finished. A report that arrives before the checking is not a report — it makes the reader part of your verification loop without telling them, and they act on it.

  The clause locks the **ordering**, because the failure was never "no review". The same review, the same lookup, moved to after the announcement, loses the thing it was for. Locked by `tests/test_protocol_floor.py::test_l10`, mutation-verified in both directions (drop the ordering sentence, drop the publishing trigger).

## [1.3.1] — 2026-09-05

### Fixed

- **The goal gate counted one target as two whenever the shell plumbing differed.** It keys each test run so it can keep the *last* result per target, but the key was the whole command line — so `cd x && sed -i … && pytest t.py` and a later bare `pytest t.py | tail -4` landed under different keys, the red one never received its green, and the streak climbed on a goal that had already been reached. It blocked this gate's own author three times in one day, each time on work that was finished. The key is now the test invocation itself: the pipeline or redirection you view it through and the `cd`/`sed` you reached it with are not part of it. The shelf entry still records the command as it was actually typed — the key exists to recognise a target, not to describe it.

### Changed

- **This repo now opts itself into its own wiring gate.** Up to 1.3.0 the gate guarded other people's repositories and not the one that ships it — which is the failure it exists to catch. `.claude/wiring-guards` lists the two general guards (every hook must appear in the health check's list; INSTALL step 5's table must match that list) and runs in about 1.5 seconds on commit. The full suite stays a pre-push responsibility; this gate only promises that the wiring class cannot slip through.

## [1.3.0] — 2026-09-05

### Added

- **The wiring gate now finds the repos nobody opted in.** Opt-in has a failure mode that mirrors the one the gate exists for: it does nothing, forever, in every repository somebody meant to enable it in and forgot. When a `git commit` happens in a repo with **no** declaration, the gate now asks `git ls-files` whether that repo already contains guards of the shape it protects — a test file whose name carries both a test word and a wiring word (`test_*_gate.py`, `test_wired_*.ts`, …). If it finds some, it leaves a note; the `SessionStart` hook reads that note and says so once, in the session where you can act on it. Opting the repo in clears the note.

  **It is a note on disk rather than a message from the gate itself, and that is not an implementation detail.** A `PreToolUse` hook has no way to say anything without also blocking: `permissionDecision: "allow"` discards its reason, and stderr on exit 0 is thrown away. An earlier version of this idea did write to stderr — the hint reached nobody while the "already hinted" stamp was written anyway, which is a mechanism that looks like it is protecting you and is not there at all. `SessionStart` output does reach the model, so that is where it goes.

  The scan runs only on a commit command in a repo without a declaration, keys on file names rather than contents, and caps at eight results. Failing to write the note never affects the commit.

## [1.2.0] — 2026-09-05

> **Verified on Windows only**, same as 1.1.0. Both new gates are unit-tested against real files and real transcripts; neither has been exercised on macOS or Linux.

### Added

- **Wiring gate** (component 4, `.claude/hooks/wiring_gate.py` + `wiring_runner.sh`, `PreToolUse` on `Bash|PowerShell`) — a second rung on the same ladder as `verify_gate`. `verify_gate` catches *changed code, no test run*; this catches the next failure along: **the test ran, it passed, and the thing it guards is not on any execution path.**

  That failure is worse than not doing the work at all. Undone work stays on the list; work that shipped gets ticked off, and the gap it was supposed to cover is then unwatched. Four instances surfaced in one repository in a single day (2026-09-05): a rate limiter carrying a `WIRING_TODO` with zero production calls for two months; a script to remove a deprecated scheduled task that never ran once because it lacked a BOM; a maintenance-lease guard covering one of two restart paths; a rebuild primitive with no callers. All four had passed review.

  The gate is **opt-in per repository** and costs one `exists()` check in repos that have not opted in. Where a repo ships `.claude/wiring-guards`, a `git commit` is blocked when the installed pre-commit hook would never run that declaration (`.git/hooks/` is not version controlled, so after a re-clone every guard file is present and none of them execute), and `--no-verify` is refused because it skips the hook without leaving a trace in git history. `ALLOW_UNWIRED=1 git commit ...` states an exception on the record.

  **The two halves enforce differently, and the difference matters.** `wiring_runner.sh` is a git hook: git runs it, so it covers every committer — the agent's Bash tool, its PowerShell tool, a human's terminal, a subagent — and no way of phrasing the command avoids it. The `PreToolUse` half reads a command string before it runs, which is a best-effort reading and cannot be complete: three rounds of adversarial review found it missing multi-line commands, leading global options (`git --no-pager commit`), quoted flags, prefix abbreviations (`--no-veri`) and per-invocation `-C`/`-c`. All of those are fixed and tested, and the ones that remain are structural — a commit reached through `eval`, `sh -c`, `xargs`, `Start-Process` or a git alias is invisible to any string inspection. Treat it as an early warning that saves you a round trip, not as the enforcement.

  `wiring_runner.sh` is the per-repo pre-commit runner. It closes three silent-skip holes found in review, each of which made the runner report **green while skipping guards**: `eval` inheriting the declaration file as stdin (one guard that reads stdin swallowed every remaining line), a final line with no trailing newline (last guard skipped), and a `pytest` invocation exiting 0 having run nothing (bad path, all skipped, over-filtered by `-k`).

- **Goal gate** (component 5, `.claude/hooks/goal_gate.py`, `Stop` + `UserPromptSubmit`) — the rung after that: **it is wired, it runs, and the goal still is not met.**

  The first failure is normal work — find the cause, fix, retest. The second is the interesting one: it means the root cause you named is probably not the root cause, and a third attempt built on the same reading is the same attempt wearing different clothes. So at two consecutive failures the gate blocks once and requires an adversarial review of the root-cause claim before the next attempt. At three it stops the item outright, writes the shelf entry itself, and tells you to move to work that does not depend on it.

  Two design points, both learned the hard way:

  - **The gate writes the shelf entry, the agent does not.** Anything that depends on an agent remembering to record something is the exact failure this ladder exists to remove.
  - **The nag is bounded.** Blocking is triggered by a shelved entry whose `note` is still empty, not by "this turn didn't mention it". The latter fires on every unrelated turn until the shelf is cleared, and a gate that nags gets bypassed. Filling in the note is a one-time act that ends the blocking permanently, which is what makes it enforceable.

  Failure detection keys on **the last test summary line in the output** (`12 passed in 1.2s`, `1 failed, 11 passed`, `3 errors in 0.5s`), not on "did anything fail anywhere in this turn". That earlier reading fired on the two practices this protocol itself mandates, both red-then-green by construction: mutation testing and fail-then-pass evidence. It blocked its own author twice on the day it was written — once on three deliberate mutations of a working guard, and again when a whole break-run-restore-run cycle arrived as **one** shell call with its outputs concatenated, which no per-command keying can split. Where there is no summary line at all — script-style tests that raise and print only a traceback — it falls back to soft markers (`AssertionError`, `FAILED …`), which also occur in passing runs and therefore only decide when nothing better is available. It errs toward "not failed": a false positive fires during normal work, and that is how gates get disabled.

  Thresholds are configurable (`FABLE_GOAL_ADVERSARIAL_AT`, `FABLE_GOAL_SHELVE_AT`) because a suite that takes 3 seconds and one that takes 30 minutes do not deserve the same patience. State lives in `<repo>/.fable/goal_state.json`, now gitignored.

  This counter is about **the goal** and is deliberately a fourth counter, separate from the three already in the governance skills — same method twice (`cognitive-rubrics`), same error twice (same skill), a subagent's first substantively wrong result (`model-dispatch-rules`). Those skills state three times that the counters must not be merged; this one honours that.

- **Protocol §4b** — the behavioural half of the goal ladder, including "when the user comes back, raise the shelved items before resuming anything". §4 also gains the behavioural half of the wiring gate: shipping something that only matters when it is called requires a test asserting **it is on an execution path**. Both are locked by `tests/test_protocol_floor.py` (L7–L9, mutation-verified).

- **tests/test_wiring_gate.py** (57 cases as released) and **tests/test_goal_gate.py** (40), all driving the real hook files and real JSONL transcripts rather than a copy of their logic. Nine mutations verified between them — for the wiring gate: un-stripping commit message bodies (a commit whose *message* mentions `--amend` silently disarmed the whole gate, and the commit that shipped this mechanism was exactly that), removing the wiring check, removing `</dev/null`, removing the trailing-newline handling; for the goal gate: not resetting the streak on green (the counter becomes a ratchet and eventually fires on unrelated work), not writing the shelf entry, not resetting after shelving (the next goal starts already at strike three), nagging on "didn't mention it" instead of the empty note, and dropping the `stop_hook_active` pass-through (which could deadlock a session).

### Fixed

Both gates were put through the kit's own three-opponent review before release — twice, because the first round's fixes turned out to need a review of their own. Sixteen defects between them, each fix shipping with a test and a verified mutation.

The most serious was found in the second round: **a `git commit` on any line but the first was invisible to the wiring gate.** The pattern that recognises the command accepted `;`, `&&` and a pipe as what precedes it, but not a newline — so `git add -A` followed by a newline and `git commit --no-verify` was not examined at all. Multi-line shell is the ordinary way an agent writes a command, which means the gate had been closer to decorative than to enforcing. Continuations (`\` and a backtick before a newline) join their lines before analysis for the same reason.

- **The wiring gate read flags from the whole command line, and short flags only in their unclustered form.** Three consequences, all reproduced: `git commit -nm "x"` was let through (`-nm` *is* `-n -m`); `git commit --amend --no-verify` was let through because `--amend` was tested first and returned early; and `git commit -m "x" && git log -n 1` was **denied** — the `-n` belonged to `git log`. The false deny was the worst of the three: a gate that fires on ordinary work gets switched off. Flags are now read from the `git commit` segment only, clusters are decoded, and `--no-verify` is checked before `--amend`.

- **The wiring gate assembled `<root>/.git/hooks/pre-commit` as a string.** In a worktree or submodule `.git` is a *file*, so that path never exists: every commit in an opted-in repo was denied, and the remedy the denial printed (`cp … .git/hooks/pre-commit`) could not be carried out there. With `core.hooksPath` set (husky, lefthook) the error runs the other way — the path exists while git reads a different one, passing a repo whose guards never run. It now asks git: `git rev-parse --git-path hooks/pre-commit`.

- **The runner reported green when it had run nothing.** An unreadable declaration made the read loop execute zero times and still exit 0; a declaration containing only comments did the same while looking like a gate. Both are red now — the same rule the runner already applied to a pytest run with nothing passed.

- **The goal gate overwrote a state file it could not read.** `load_state` returned an empty state on any error and the next write replaced the whole file, so a truncated or locked `goal_state.json` silently discarded the shelf, including notes written by hand. A missing file is still a fresh start; an unreadable one is now left alone.

- **A run with no tests cleared the streak.** `pytest -k nomatch` prints `no tests ran` and exits 0; counting that as a pass reset the ladder, so a goal that failed, ran something vacuous, then failed again never reached the second rung. A vacuous run is now neither a pass nor a failure.

- **Mentioning a shelved item's id satisfied the shelf gate without writing the note.** Since §4b instructs the agent to raise shelved items when the user returns, the protocol's own instruction was the unlock code, and the note was never written. The empty note is now the only trigger — as this changelog already described it.

- **Every `key=value` in a stored command is masked.** `GITHUB_TOKEN=… pytest` matches the test-command pattern, and the command is both written to a file inside the user's repo and read back into the conversation on the next turn. Masking only the leading assignment left `cd r && TOKEN=… pytest`, `env TOKEN=… pytest` and `pytest --db-url=postgres://u:p@h/db` in the clear. Keys stay visible so the command is still recognisable.

- **The state directory now ignores itself.** `.fable/` holds the user's failing commands and lands in *their* repository; telling them to add it to `.gitignore` (INSTALL step 11) only helps the people who read that step, and a repo without a `.gitignore` would have committed it on the next `git add -A`. The directory now carries its own `.gitignore`. The temp file used for atomic writes also carries the process id — two sessions in one repo shared a single `goal_state.json.tmp`.

- **Short flags are decoded as flags, not searched as text.** `-nm` is `-n -m`, but `-Sjohn` is `-S` with a key id that merely contains an `n`, and matching the letter anywhere denied that commit. The scan now walks each token and stops at the first value-taking flag.

- **A one-shot `-c` is honoured when asking git where hooks live.** `git -c core.hooksPath=/dev/null commit` points git at a directory with no pre-commit and leaves no configuration behind; asking `git rev-parse` *without* that same `-c` answered for a different configuration and passed the commit. `git -C <path> commit` likewise acts on `<path>`, not on the session's directory, and the declaration that matters is the one over there.

- **The runner's new red states route through the existing escape.** An unreadable or guard-less declaration made it exit non-zero *before* the `ALLOW_UNWIRED=1` check — and since `--no-verify` is blocked too, that combination left a repository with no way to commit at all. A gate with no exit is a gate people delete.

- **An unreadable state file now says so.** Refusing to overwrite it protects the shelf, but staying silent about it left the whole component doing nothing with no way to find out — precisely the failure this ladder exists to remove.

- **A vacuous run is judged on the same line as everything else.** Reading "no tests ran" from anywhere in the output meant a guard printing `[wiring] no tests ran` before `12 passed` counted as vacuous, so a genuine green stopped clearing the streak. Fail, pass and vacuous are now all decided by the last summary line.

### Changed

- **Health check** (`scripts/fable_doctor.py`) now tracks **(event, script) pairs instead of one script per event** — `goal_gate.py` is registered on two events, and `UserPromptSubmit` now hosts two scripts. Keyed by event alone, the second script on an event is invisible to the doctor: not reported as missing, simply never looked at. Trigger markers are keyed by script for the same reason — otherwise `goal_gate.py` would inherit `prompt_nudge.sh`'s "last ran" timestamp and appear verified on another script's evidence.

- **Health check also reports which clone a hook runs from** (`hook-elsewhere`). Matching on the file name alone called a hook "registered" while the command pointed at a *different* checkout of this kit — the reported version and copied skills then describe one directory while the executing code lives in another, with nothing in the report showing it. That state existed on the author's own machine while this release was being assembled.

- **New general guards** in `tests/test_fable_doctor.py`: `test_d9` — every Claude hook script in `.claude/hooks/` must appear in the doctor's list; `test_d11` — the six rows of INSTALL.md step 5 must match that list exactly, so the document and the health check cannot drift apart when a component is added. Written as a rule rather than an assertion about these two hooks, so the *next* component cannot ship invisible to the health check; `wiring_runner.sh` is excluded because it is a git hook, not a registered Claude hook.

- **The default README is now Traditional Chinese** (`README.md`); the English text moved to `README.en.md`. The language switcher at the top of all five translations points at the new locations, and the badges read 1.2.0.

- **INSTALL.md**: step 5 now registers six entries (five scripts, `goal_gate.py` twice) with an explicit matcher column; new steps 10 and 11 cover the per-repo wiring opt-in and the goal-gate thresholds, each with a way to verify it that does not require waiting for a real failure. Uninstall gains the per-repo leftovers (`.claude/wiring-guards`, `.git/hooks/pre-commit`, `.fable/`) that removing `~/.claude` alone does not clean up.

## [1.1.0] — 2026-08-27

> **Verified on Windows only.** The install flow, the three hooks and the health check were exercised end to end on Windows. macOS and Linux are expected to work — `INSTALL.md` branches its interpreter detection for them — but neither was run. `scripts/fable_doctor.py` is the way to find out on your own machine.

### Added

- **Health check** (`scripts/fable_doctor.py`): reports which interpreter each of the three hooks actually resolves to, when each last fired, whether the copied skill and agents still match the repo, and whether the recorded install version is behind. Every hook command ends with `|| exit 0`, so a missing or wrong interpreter previously produced no error, no log line, and nothing an install could distinguish from success — this is where that becomes visible. Covered by `tests/test_fable_doctor.py` (9 cases).
- **Upgrade section** in `INSTALL.md`: the hooks are referenced by path and update on `git pull`, but the skill and agents are copies and do not. That drift was undocumented and undetectable across three released versions. An install marker (`~/.claude/fable-harness-install.json`) now records the installed version so the doctor can flag it.
- **The two governance docs are now skills** and therefore reach every project. `model_dispatch_rules.md` → `.claude/skills/model-dispatch-rules/SKILL.md`, `cognitive_rubrics.md` → `.claude/skills/cognitive-rubrics/SKILL.md`. Before this they were only reachable through this repo's own `CLAUDE.md` routing table, which is not installed anywhere — so outside this repo they were advertised in the README and unreadable in practice. A personal skill is available across all your projects, and a skill's body loads only when it is used, so the 182 lines cost nothing until the model needs them. `INSTALL.md` step 8 now copies all three skills.
- **Public governance test** (`tests/test_protocol_floor.py`): a portable content lock on the injected protocol floor, so a fresh clone can re-run at least one governance check rather than none.

### Changed

- **Verification gate** (`.claude/hooks/verify_gate.py`): now counts code changed through the shell — `sed -i`, a redirect, `tee` — not only `Edit`/`Write`/`NotebookEdit`. Measured across the 30 most recent real transcripts: Bash was used 6989 times against 813 `Edit`s and 387 `Write`s, and 887 of those shell calls had the shape of a file write, so roughly a third of all code changes were happening where the gate could not see them. It keys on the *write target's* extension, so `grep -n foo src/bar.py > out.txt` reads Python, writes text, and stays out of scope; writes into a temp or scratchpad path are ignored. False-positive rate on the same data: 149 of 7058 commands, 2.1%. Adds T13–T16. `MultiEdit` was considered and rejected on the same measurement — it appears in 4 of 103 transcripts and 0 of the recent 30.
- **Health check** now watches all three skill copies, not only `adversarial-review` — the two governance docs became copy-delivered in this release, which is exactly the drift the doctor exists to catch.
- **Governance skills**: the six remaining clauses that assumed the project already owns test tooling or version control are rewritten so they hold in a project that has neither. The slow-down trigger leads with the general rule (will this run when nobody is watching) instead of a fixed list of tools; acceptance criteria and the report template's evidence field accept any re-runnable verification, not only a test command; out-of-scope recovery names git as the version-controlled path and falls back to the backup the previous step already requires. Locked by `tests/test_skill_delivery.py`, which also locks each skill's frontmatter — a skill's body loads only when its description makes it look relevant, so a blunted description leaves the skill present, the tests green, and the rules never loaded.
- **Install** (`INSTALL.md`): a missing `settings.json` now creates a minimal one instead of aborting — a brand-new machine is the main case this kit is for, and the old rule (written to protect an existing-but-broken file) caught both situations. Step 5 now requires detecting the interpreters before writing any command string, with OS branches and a template, calling out the two traps seen in practice: only `python3` existing, and a bare `bash` on Windows resolving to the WSL launcher rather than Git Bash. Step 9 now verifies all three hooks instead of only `SessionStart`, using the marker files rather than whether the nudge line happens to be visible in a given client.
- **Protocol** (`.claude/hooks/fable_protocol.md` §3): progress is reported with two values, done and not started. "In progress" is no longer a permitted state — a reply is written and sent in one moment, so unless something was actually launched there is nothing running behind it. When there is real background work, the rule asks for a statement of what has already happened plus what follows when it returns.

## [1.0.2] — 2026-07-20

### Fixed

- **verify_gate**: force UTF-8 stdout (`sys.stdout.reconfigure`) so the block JSON — whose reason string opens with "⛔" — survives Windows consoles that default to a legacy codepage (e.g. cp950). Without it `print()` raised `UnicodeEncodeError`, the fail-open handler swallowed it, and the Stop gate silently never blocked. Landed via [#2](https://github.com/Miguok/fable-harness/pull/2) by [@lepus071](https://github.com/lepus071).
- **verify_gate**: the fail-open handler no longer swallows failures silently — before returning it appends one sanitized post-mortem line (exception class + bounded message, never the raw payload) to a gitignored `.gate_fail`, in a nested try so the telemetry can never break fail-open, and bounded to keep the earliest incident lines. A silently-dying gate is now observable — that exact failure mode is what hid the cp950 bug for days. Adds test T12 (fail-then-pass verified). Idea from [@Atistw](https://github.com/Atistw) in [#3](https://github.com/Miguok/fable-harness/pull/3).

### Added

- **Maintainer guide** (`MAINTAINING.md`, + 繁體中文 translation): the PR merge SOP for keeping the contributor list clean — squash-merge and drop the `Co-Authored-By: Claude <noreply@…>` trailer so no phantom contributor appears.

### Changed

- **Docs**: the README "How it works" section (all five languages) now documents the token efficiency that falls out of the architecture — tiered model routing plus context-isolated, parallel sub-agents — noting that no Fable-specific benchmark figure is claimed.

## [1.0.1] — 2026-07-07

### Fixed

- **verify_gate**: `TEST_CMD_RE` now recognizes script self-test entrypoints — a `--test` flag on any command (e.g. `python3 zh_convert_safe.py --test`) counts as a test run, so the Stop gate no longer falsely blocks a turn that ran one. Look-alike flags (`--test-pypi`, `--testing`, `--tests`) stay blocked via a `(\s|$)` anchor. Adds test T11 (allow + block cases, fail-then-pass verified). Reported by [@Jia-Hong-Peng](https://github.com/Jia-Hong-Peng) in [#1](https://github.com/Miguok/fable-harness/pull/1).

## [1.0.0] — 2026-07-07

First tagged release. The kit is feature-complete and globally deployed.

### Included

- **Behavior protocol** injected at session start (`.claude/hooks/fable_protocol.md` + `inject_protocol.sh`), codename `FABLE-PROTOCOL-V1-CANARY`.
- **Per-turn nudge** (`.claude/hooks/prompt_nudge.sh`) and **verification gate** (`.claude/hooks/verify_gate.py`) with native cross-scope de-duplication.
- **Adversarial review** skill (`.claude/skills/adversarial-review/`) and the three opposition agents (`skeptic`, `red-team`, `simplifier`).
- **Model routing** table (`CLAUDE.md`) and **harness detector** (`scripts/detect_harness.py`).
- **Governance docs**: `model_dispatch_rules.md`, `cognitive_rubrics.md`.
- **Docs**: `README.md` and translations (繁體中文 / 简体中文 / 日本語 / 한국어), `INSTALL.md`, MIT `LICENSE` (+ 繁體中文 translation).
