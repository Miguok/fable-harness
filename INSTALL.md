# Installing Fable Harness

This kit doesn't ship a one-click installer. Instead, you clone the repo and then **ask your own Claude Code to install it**, following the steps below. Claude is good at doing careful, checked file operations — that's the whole point of this kit — so it can safely install itself.

安裝會動到你電腦上 Claude Code 的個人設定檔，請務必讓 Claude 先備份、只用「新增」而非「覆蓋」的方式合併，並在裝完後驗證成功。

## Prerequisite

Clone this repo anywhere on your machine, for example:

```bash
git clone <this-repo-url> fable-harness
```

You don't need to put it in any special location — just remember the path, since the global hooks will point back at it.

## Install

Open Claude Code inside (or pointed at) the cloned repo, and say:

> Install Fable Harness by following INSTALL.md.

Claude should then carry out the following steps, in order. If you're Claude reading this: treat every step as a safety-critical file operation. Do not skip the backup or verification steps, and stop and ask the user if anything looks ambiguous (existing hooks you don't recognize, a settings file that won't parse, a symlinked directory, etc).

1. **Find the repo's own absolute path.** Run `pwd` (or equivalent) inside the cloned repo. You'll need this absolute path later — the hooks are referenced by path, not copied, so this repo must stay where it is after install.

2. **Find the user's global Claude config directory.**
   - macOS / Linux: `$HOME/.claude`
   - Windows: `%USERPROFILE%\.claude` (e.g. `C:\Users\<name>\.claude`)

3. **Read and validate `~/.claude/settings.json` before touching anything.** Two different situations get two different answers — don't collapse them:
   - **It does not exist** (the normal state of a brand-new machine): create a minimal one containing only `{"hooks": {}}`, tell the user you created it, and carry on. A fresh machine is exactly who this kit is for; stopping here would block the main case.
   - **It exists but is empty or fails to parse as JSON**: **stop and tell the user.** Do not overwrite it and do not guess defaults — installing on top of a broken settings file risks silently discarding configuration that is still in there.

4. **Back up `settings.json`** to a timestamped copy (e.g. `~/.claude/backups/settings.json.bak_<timestamp>`) before making any change. Confirm the backup file actually exists on disk before proceeding.

5. **Merge in three hooks — additively, never destructively.** Add these three entries to the `hooks` section, pointing at the scripts inside *this cloned repo* (use the absolute path from step 1, not a copy):

   | Event | Script | What it does |
   |---|---|---|
   | `SessionStart` | `<repo>/.claude/hooks/inject_protocol.sh` | Injects the behavior protocol at session start |
   | `UserPromptSubmit` | `<repo>/.claude/hooks/prompt_nudge.sh` | Injects a one-line reminder on every user turn |
   | `Stop` | `<repo>/.claude/hooks/verify_gate.py` | Blocks ending a turn where code changed but no test ran |

   **Before you write any command string, find the interpreters that actually work on this machine. Do not assume `bash` and `python` are on PATH, and do not assume they're the ones you want.**

   - **macOS / Linux**: `command -v python3`, then `command -v python` as a fallback; `command -v bash`.
   - **Windows**: PowerShell has no `command -v` — use `Get-Command python -ErrorAction SilentlyContinue` or `where.exe python`. Two traps here, both observed in the wild:
     - `python` may not exist at all even though `py` does, and on many systems only `python3` exists.
     - **A bare `bash` on Windows often resolves to the WSL launcher**, not the Git Bash these scripts are written for. Check what you actually got: `bash -c 'echo ok'` must print `ok`, and the resolved path should look like `C:\Program Files\Git\bin\bash.exe`.
   - **Then prove it before writing it down.** Run each of the three scripts once by hand with the interpreter you found. `inject_protocol.sh` should print the protocol; `prompt_nudge.sh` should print one line; `verify_gate.py` should accept JSON on stdin and exit without a traceback. An interpreter that resolves but can't run the script is worse than one that's missing, because it looks fine.

   Use the **absolute path you verified**, quoted, in the command string — the repo may live under a path with spaces or non-ASCII characters:

   ```
   "<abs-path-to-bash>" "<repo>/.claude/hooks/inject_protocol.sh" || exit 0
   "<abs-path-to-bash>" "<repo>/.claude/hooks/prompt_nudge.sh" || exit 0
   "<abs-path-to-python>" "<repo>/.claude/hooks/verify_gate.py" || exit 0
   ```

   ⚠ **What `|| exit 0` costs you.** It stops a broken hook from wedging the session — but it also makes "the interpreter doesn't exist" look *exactly* like "the hook ran fine". Nothing is printed, nothing is logged, and the kit appears installed while doing nothing at all. That is why step 9 verifies all three hooks rather than one, and why `scripts/fable_doctor.py` exists.

   Rules for this step:
   - Only **append** these three. Never remove, reorder, or rewrite any hook, model setting, theme, or other key the user already has.
   - If any of these three already exist (installed before), skip re-adding it — this step must be idempotent (safe to run twice).
   - After merging, verify every pre-existing top-level key and every pre-existing hook entry is still present and unchanged. If anything is missing, abort and restore from the step-4 backup.
   - Write via a temp file + atomic rename, not a direct in-place overwrite, so a crash mid-write can't corrupt the user's settings.

6. **Watch out for symlinks.** Some users manage `~/.claude/hooks`, `~/.claude/skills`, `~/.claude/agents`, or `~/.claude/CLAUDE.md` as symlinks (or Windows junctions) into a separate dotfiles/config repo. Before writing into any of these directories, check whether the target — or its parent — resolves (via realpath, not just `is_symlink`, since Windows junctions can hide from that check) to somewhere unexpected. If it does, **don't write through it silently** — tell the user what you found and ask where they'd like the files to actually land.

7. **Command strings must match exactly if they exist in more than one place.** If this project's own `.claude/settings.json` *also* defines these same three hooks (e.g. because you were developing inside this repo), the command string in the project settings and in the global settings must be **character-for-character identical**. Claude Code's native de-duplication relies on this — a stray difference (like a missing `|| exit 0` fallback) will cause the hook to fire twice per event instead of once.

8. **Copy the three skills and the three agents.**
   - Copy each of `<repo>/.claude/skills/adversarial-review/`, `<repo>/.claude/skills/cognitive-rubrics/`, and `<repo>/.claude/skills/model-dispatch-rules/` to the matching directory under `~/.claude/skills/`.
     A personal skill is available across all your projects, and a skill's body loads only when it's used — so the two governance skills (99 and 83 lines) cost nothing until the model actually needs them.
   - Copy `<repo>/.claude/agents/skeptic.md`, `red-team.md`, and `simplifier.md` to `~/.claude/agents/`.
   - If any destination already exists, don't overwrite it — stop and ask the user first.
   - **Then write an install marker** at `~/.claude/fable-harness-install.json` containing the repo's absolute path, the contents of `<repo>/VERSION`, and the install date. The hooks are referenced by path and update themselves when you `git pull`; the skill and agents are **copies** and do not. This marker is the only thing that makes that drift detectable — see [Upgrade](#upgrade).

9. **Verify all three hooks — not just one.** Each hook fails silently and independently, so one passing check proves nothing about the other two.

   1. **`SessionStart`** — start a brand-new Claude Code session and ask: *"What's your protocol codename?"* It should answer `FABLE-PROTOCOL-V1-CANARY`.
   2. **`UserPromptSubmit`** — check that `<repo>/.claude/hooks/.last_promptsubmit` has a timestamp from the turn you just took. (Read the marker file; don't rely on whether the nudge line is visible in your client's UI — that varies.)
   3. **`Stop`** — in a **scratch directory, not the user's project**, create a throwaway `sample.py`, edit it with the Edit tool, then try to end the turn without running any test. The gate should block you once. Delete the scratch directory afterwards.

   If any of the three doesn't fire, run `python <repo>/scripts/fable_doctor.py` — it reports which interpreter each hook resolved to, when each hook last ran, and whether the installed copies match the repo.


## Upgrade

**This kit updates itself only halfway, and the half that doesn't is invisible.** The three hooks are registered by *path*, so `git pull` in the cloned repo updates them immediately. The skill and the three agents were **copied** into `~/.claude/` at install time, so they stay on whatever version you first installed — including the wording of the adversarial-review procedure the model actually follows.

To upgrade:

1. `git pull` in the cloned repo. The hooks are now current; nothing else is.
2. **Re-copy the three skills and the three agents**, overwriting the existing ones — every directory under `<repo>/.claude/skills/` → `~/.claude/skills/`, and `skeptic.md` / `red-team.md` / `simplifier.md` → `~/.claude/agents/`.
   ⚠ This is the one place where overwriting is correct. Step 8's "don't overwrite, stop and ask" protects you from clobbering *someone else's* file during a first install; on an upgrade you are replacing **your own** older copy of this kit's file. If you are not sure which situation you're in, run the doctor below — `copy-drift` means it's yours and it's stale.
3. **Update the install marker** `~/.claude/fable-harness-install.json` with the new contents of `<repo>/VERSION`.
4. Run the health check and confirm it comes back clean.

## Health check

```bash
python <repo>/scripts/fable_doctor.py --home ~ --repo <repo>
```

It reports, for each of the three hooks, **which interpreter the registered command actually resolves to** and when that hook last fired — plus whether your copied skill and agents still match the repo, and whether the recorded version is behind. It exits `1` if it found anything.

This is the only place several of these failures are visible at all: every hook command ends with `|| exit 0`, so a missing or wrong interpreter produces no error, no log line, and no difference you could notice from inside a session.

## Optional: tidy up your global CLAUDE.md

If you already have a `~/.claude/CLAUDE.md` with your own development philosophy notes, some of it may now overlap with what the injected protocol already covers (the OODA loop, the definition of done, etc). You can ask Claude to read your global `CLAUDE.md` and shrink any rules that duplicate the injected `FABLE-PROTOCOL` down to a short pointer — while keeping anything that's uniquely yours. This step is optional and purely about reducing duplication; nothing in this kit requires it.

## Uninstall

To remove Fable Harness:

1. Open `~/.claude/settings.json` and delete the three hook entries listed in step 5 above (`SessionStart` → `inject_protocol.sh`, `UserPromptSubmit` → `prompt_nudge.sh`, `Stop` → `verify_gate.py`). Leave everything else untouched.
2. Delete `~/.claude/skills/adversarial-review/`, the three files in `~/.claude/agents/` (`skeptic.md`, `red-team.md`, `simplifier.md`), and the install marker `~/.claude/fable-harness-install.json`.
3. If you edited your global `CLAUDE.md` in the optional step above and want the old wording back, restore it from your own version history or notes.

You can always ask Claude to do this for you too — the same care applies: back up `settings.json` first, then remove only the entries that belong to this kit.
