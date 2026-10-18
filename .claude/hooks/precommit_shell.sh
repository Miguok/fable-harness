#!/bin/sh
# Fable wiring gate — thin pre-commit shell. It runs the runner committed on
# Fable's main branch, so there is no copy to drift. Install: INSTALL.md step 10.
F="@FABLE@"
# Same opt-in rule as the runner: no declaration, nothing to run — and no need
# to reach Fable at all.
[ -f .claude/wiring-guards ] || exit 0
red() {
    echo "[wiring] RED: $1" >&2
    echo "[wiring] Fix: $2" >&2
    if [ "${ALLOW_UNWIRED:-}" = "1" ]; then
        echo "[wiring] ALLOW_UNWIRED=1 — unwired state accepted on the record" >&2
        exit 0
    fi
    echo "[wiring] To defer on the record: ALLOW_UNWIRED=1 git commit ..." >&2
    exit 1
}
fix_f="set F= in $0 to your Fable clone (INSTALL.md step 10)"
# Pin the repository to "$F/.git": git exports GIT_DIR & co. to hooks (linked
# worktree, --git-dir), and plain discovery walks up past a non-repo "$F" —
# either way it would read the committing repo instead of Fable.
fg() {
    env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR \
        -u GIT_OBJECT_DIRECTORY -u GIT_ALTERNATE_OBJECT_DIRECTORIES \
        git --git-dir="$F/.git" "$@"
}
# Resolve first: `refs/heads/main:<path>` is rewritten by MSYS path conversion,
# and a bare `main` would also match a tag.
c=$(fg rev-parse --verify -q 'refs/heads/main^{commit}') || red "no main branch in $F" "$fix_f"
s=$(fg cat-file blob "$c:.claude/hooks/wiring_runner.sh") || red "runner unreadable on $F main" "$fix_f"
# A runner emptied out or reduced to `exit 0` also returns 0, so rc alone proves
# nothing. The runner reports on fd 3 only after it ran at least one guard; its
# own stdout goes to stderr so the user still sees every line.
proof=$(sh -c "$s" wiring_runner .claude/wiring-guards --receipt 3>&1 1>&2) || red "the runner on $F main reported red or failed" "see the output above"
[ "$proof" = "FABLE_WIRING_V1_RAN" ] || red "runner did not confirm guard execution" "check .claude/hooks/wiring_runner.sh on $F main (it must report FABLE_WIRING_V1_RAN on fd 3)"
