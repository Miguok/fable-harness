#!/bin/sh
# install_precommit.sh <fable-path> — install the thin pre-commit shell into the repo in the cwd.
# Replaces only this kit's own hooks (backed up first); refuses anything else.
[ -n "$1" ] || { echo "usage: install_precommit.sh <path to your Fable clone>" >&2; exit 2; }
# Absolute, so the hook resolves the same from every worktree; must be a git
# clone, because the hook reads the runner from its main branch.
FAB=$(cd "$(printf '%s' "$1" | tr '\\' '/')" 2>/dev/null && { pwd -W 2>/dev/null || pwd; }) &&
    [ -e "$FAB/.git" ] || { echo "not a git clone of Fable: $1" >&2; exit 1; }
# The template comes from Fable's main branch, like the runner — never from its
# working tree, where a half-finished edit would be installed everywhere.
fg() {
    env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR \
        -u GIT_OBJECT_DIRECTORY -u GIT_ALTERNATE_OBJECT_DIRECTORIES \
        git --git-dir="$FAB/.git" "$@"
}
c=$(fg rev-parse --verify -q 'refs/heads/main^{commit}') &&
    tpl=$(fg cat-file blob "$c:.claude/hooks/precommit_shell.sh") || { echo "template not found on main of $FAB" >&2; exit 1; }
# F= sits inside double quotes in the shell; these would change its meaning.
case "$FAB" in *[\"\$\`]*) echo "unsupported character in path: $FAB" >&2; exit 1 ;; esac
# Set at all — even to "" — moves the hooks somewhere this script must not guess.
if git config --get core.hooksPath >/dev/null 2>&1; then
    echo "core.hooksPath is set: integrate by hand (INSTALL.md step 10)" >&2; exit 1
fi
D=$(git rev-parse --git-path hooks 2>/dev/null) || { echo "run this inside the repo to protect" >&2; exit 1; }
mkdir -p "$D" || { echo "cannot create hooks directory: $D" >&2; exit 1; }
H="$D/pre-commit"
if [ -e "$H" ] || [ -L "$H" ]; then
    # `-f` follows symlinks, so test `-L` first: a link would be replaced by a
    # plain file and its backup would hold the target, not the link.
    { [ ! -L "$H" ] && [ -f "$H" ]; } ||
        { echo "existing pre-commit is not a regular file: integrate by hand (INSTALL.md step 10)" >&2; exit 1; }
    sed -n 2p "$H" | grep -q -e "^# Fable wiring gate" -e "^# wiring_runner.sh — git pre-commit runner" ||
        { echo "existing pre-commit is not from Fable: integrate by hand (INSTALL.md step 10)" >&2; exit 1; }
    B="$H.bak.$(date +%Y%m%d-%H%M%S)"
    [ -e "$B" ] && { echo "backup $B already exists; rerun in a second" >&2; exit 1; }
    cp "$H" "$B" || { echo "backup failed; nothing replaced" >&2; exit 1; }
    echo "previous pre-commit backed up to $B" >&2
fi
esc=$(printf '%s' "$FAB" | sed 's/[&|\\]/\\&/g')
fail() { echo "$1" >&2; rm -f "$H.tmp"; exit 1; }
printf '%s\n' "$tpl" | sed "s|@FABLE@|$esc|" > "$H.tmp" || fail "could not write $H.tmp"
# Refuse to install a shell whose F= is not exactly the path given.
grep -qxF "F=\"$FAB\"" "$H.tmp" || fail "path substitution failed for: $FAB"
chmod +x "$H.tmp" && mv -f "$H.tmp" "$H" || fail "could not install $H"
