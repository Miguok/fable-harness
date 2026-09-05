# Maintaining Fable Harness

**English** &nbsp;·&nbsp; [繁體中文](MAINTAINING.zh-TW.md)

Notes for maintainers of this repository. You don't need this to *use* the kit — see [README](README.en.md) and [INSTALL.md](INSTALL.md) for that.

## Reviewing a PR that touches `.claude/wiring-guards`

That file is a list of shell commands, and the pre-commit runner `eval`s every
line of it. A change to it is a change to what runs on the machine of everyone
who commits after merging — read it the way you would read a change to a build
script, not the way you would read a config value. The same applies to
`.claude/hooks/wiring_runner.sh` itself.

## Reviewing a PR that touches `.claude/fable-verifier`

That file names the commands whose green result closes out a failing goal. A
line added there is an **exemption**: declare something that always passes and
the goal gate stops escalating, silently. It is in the working tree and travels
with a clone, so treat it like `.claude/wiring-guards` — a change to what the
gate will accept, not a config value.

This is a deliberate trade. What it replaced was the gate *inferring* that a
broad green covered a narrow red, and that inference was measured wrong in six
distinct shapes. A declaration at least requires the repository to say so out
loud, in a file a reviewer can see.

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

## Releasing

`scripts/release.py` is the only supported way to publish a version. Do not run
`gh release create`, `git tag` or `git push --tags` by hand.

```sh
# 1. after the adversarial review, record it against the exact commit
python scripts/release.py --attest \
  --lenses "skeptic:REFUTED,red-team:REFUTED,simplifier:REFUTED" \
  --judge "ship"

# 2. dry run — preconditions only
python scripts/release.py 1.5.0 --check

# 3. publish
python scripts/release.py 1.5.0
```

It refuses unless the tree is clean, `VERSION` matches, `CHANGELOG.md` has that
section, the suite is green, and an adversarial review is recorded **for the
commit being released**. That last condition is why the attestation stores a
`reviewed_commit`: reviewing, then changing one line, then publishing would
otherwise pass a check that only asked "does a review exist".

The reason this is a script rather than a hook that watches for release commands:
`gh release create`, `git push --tags`, the GitHub API and the web UI are an
unbounded surface, and the wiring gate already spent three releases learning that
lesson on `--no-verify`. What is stable is the artifact's precondition, not the
shape of the command someone typed.

### Break-glass

```sh
python scripts/release.py 1.5.1 --override-review --reason "critical security rollback"
```

The reason is mandatory and is written into both the attestation and the release
notes, which are stamped `ADVERSARIAL_REVIEW_BYPASSED`. This exists because
without an escape hatch, someone in a genuine emergency invents a dirtier one —
and those leave no record at all.
