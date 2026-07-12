# Maintaining Fable Harness

**English** &nbsp;·&nbsp; [繁體中文](MAINTAINING.zh-TW.md)

Notes for maintainers of this repository. You don't need this to *use* the kit — see [README](README.md) and [INSTALL.md](INSTALL.md) for that.

## Keeping the contributor list clean (no `noreply` / Claude phantom)

By default, Claude Code appends a `Co-Authored-By: Claude <noreply@anthropic.com>` trailer to commits it helps write. GitHub renders that trailer as a contributor, which shows up in the repo's **Contributors** sidebar as a `noreply` / `claude` entry that isn't a real person. Two layers keep it out.

### 1. Your own commits — handled automatically

`.claude/settings.json` sets:

```json
"attribution": { "commit": "", "pr": "" }
```

This tells Claude Code not to append the co-author trailer (or a PR footer) to commits and PRs it creates in this repo, so your own commits won't create the phantom. Nothing to do per-commit.

### 2. Contributors' PRs — the merge SOP

You can't control the config a contributor used, so their PR commit may still carry the Claude trailer. Strip it at merge time.

**Always merge PRs with "Squash and merge"** — it is the only merge method that lets you edit the resulting commit message.

1. On the PR, open the merge-button dropdown and choose **Squash and merge**.
2. In the editable message box, **delete the line whose email is `noreply@anthropic.com`**, e.g.:
   ```
   Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
   ```
   The display name may be `Claude Opus …` or `Claude Fable 5` — key on the `noreply@anthropic.com` address, not the name.
3. **Keep** any `Co-authored-by:` line for a real person (e.g. `... <someone@users.noreply.github.com>`) — those are genuine collaborators and should stay credited.
4. Confirm the squash merge.

The human PR author stays credited — they remain the commit **author**, independently of any co-author line. Only the Claude phantom is removed.

CLI equivalent:

```
gh pr merge <PR> --squash --body "<clean message without the Claude line>"
```

### Why not the other merge methods

**Create a merge commit** and **Rebase and merge** replay the PR's original commits verbatim, so the Claude trailer survives and the phantom reappears. Only **Squash and merge** lets you edit the message.

### What this does *not* do

- **Not retroactive.** Commits already merged still carry whatever trailer they were made with. Removing those would mean rewriting published history, which we deliberately avoid — it breaks open PRs and forks.
- **Don't** close a good PR and re-implement it yourself just to avoid the trailer. That erases a real contributor. Merge it and strip the one line instead.
