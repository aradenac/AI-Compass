---
name: resume-stale-work-branch
description: Resume an issue whose work branch was started earlier, before its parent phase landed — the branch is stacked on an old revision whose parent has since been merged to main. Locates the existing worktree, partial-rebases the branch onto current main (git rebase --onto), fixes conflicts, syncs the GitHub issue into beads, then continues the issue per CLAUDE.md. Use for "continue the work on #n", "resume that branch", "the parent merged, pick it up again", or /resume-stale-work-branch.
---

# Resume a stale work branch

CLAUDE.md governs one issue; this skill governs the transition from a branch that
fell behind to normal work. Read CLAUDE.md first. Spec: `AGENTS.md`.

Unlike `multi-issue-delivery` (your own stacked queue advancing forward), this
branch already exists, was cut from an **older base** whose parent issue was still
under work, and that parent has **since merged to `main`** as a *squash commit* —
the branch still carries the parent's **original** commits beneath its own. Drop
those; keep only this issue's work.

The branch lives in a **worktree that already exists** — find it and continue
**in place**. Never create a new worktree or branch.

## Confirm the premise (first)
Applies only if the parent actually merged. Verify, don't assume:
- `gh pr list --state merged` (and the parent bead/PR the branch depends on) —
  the parent's PR shows MERGED.
- **Parent not merged** ⇒ this skill doesn't apply: it's a forward stack
  (`multi-issue-delivery`); rebasing onto `main` would drag/duplicate the unmerged
  parent's commits. Stop, reconsider; don't force it.
- Several merged parents stacked under the branch ⇒ base is the **top of the
  merged chain**, not `main`'s tip.

## Identify the worktree
The work is in a worktree; reuse it, don't recreate it.
1. `bd show <id>` — read `--external-ref gh-<n>` and the top checkpoint note,
   which should name the worktree dir, branch, and recorded base SHA.
2. `git worktree list` — find the dir whose branch is `agent/gh-<n>-…`.
3. Confirm it: `git -C <dir> branch --show-current` matches the bead's branch;
   `gh pr list --head <branch>` is this issue; the bare `agent/gh-<n>-…` name
   still matches this GitHub issue (CLAUDE.md §1).
4. All git below runs **inside `<dir>`** (`git -C <dir> …`).
   Worktree/branch disagreement (branch without worktree, wrong branch, two
   candidates) ⇒ doubt, arbitrate (CLAUDE.md §7), don't guess.

## Make the initial state clean
- Commit or stash **on this branch** any uncommitted work (it is this issue's;
  keep it, never discard).
- `git -C <dir> fetch origin`; confirm clean via `git -C <dir> status --short`.
- `git -C <dir> log --oneline origin/main..HEAD` — what the rebase will rewrite;
  note which commits are **this issue** vs. the **merged parent(s)**.

## Find the base to drop (`--onto` target)
The crux, because a squash-merged parent is *not* findable by SHA on `main` and
`git cherry` won't mark its commits applied. **`git merge-base HEAD origin/main`
is NOT usable**: it returns the parent's own fork point, *below* the parent's
commits — rebasing onto it keeps them. Derive the base explicitly, best source
first:
1. The recorded base in the bead's checkpoint note / `--design`
   (e.g. `ai-hcr.6` recorded `git rebase --onto origin/main 569abbb`). Use it.
2. From `git log --oneline origin/main..HEAD`: the merge boundary is the **newest
   commit belonging to a now-merged parent**. Match subjects (issue numbers,
   `(#nn)`) against `gh pr list --state merged`. At/below the boundary = parent
   (drop); above = this issue (keep). Base = boundary commit's SHA.
3. Parent issue named in the bead/PR dependency ⇒ its former branch tip is the
   base — recover from `git branch -a`, `git reflog`, or the parent PR's head.

Ambiguous boundary (subjects don't separate cleanly) ⇒ stop, arbitrate
(CLAUDE.md §7); a wrong base silently drops or keeps the wrong commits.

## Partial rebase and conflicts
- `git -C <dir> rebase --onto origin/main <base> HEAD`
  (or `<base> <branch>` checked out) — replays only **this issue's** commits onto
  current `main`.
- Conflicts are **content-level**, not SHA-level: the parent's squash-merge is
  already on `main`, so a conflict means your branch and the merged parent touched
  the same lines. Resolve as a **semantic merge** — keep the merged parent's
  accepted work **and** this issue's behavior; never revert a merged sibling's
  work to clear a conflict. Reuse primitives the parent introduced, don't
  re-declare them.
- Rules: **never** `git merge main` into the branch; **never** `--update-refs`
  (fails here); after resolving `grep -rn '<<<<<<<'` must be empty and the
  relevant syntax/lint check (e.g. `node --check`) clean.
- Do **not** push yet.

## Verify the initial state
- `git -C <dir> log --oneline origin/main..HEAD` lists **only this issue's**
  commits — no parent commits.
- `git -C <dir> merge-base HEAD origin/main` == current `origin/main` (direct
  child of main again).
- Worktree clean; conflicts resolved; syntax check clean.

## GitHub issue → beads sync (after the rebase is clean)
Reconcile beads from GitHub *before* continuing (CLAUDE.md §4):
- `gh issue view <n> --comments` — current body, acceptance, new review comments.
- Diff against the bead's `--acceptance`, `--design`, notes. Per change:
  **update** the bead (`bd note`/`bd update`), **reopen** a closed child whose fix
  is challenged, or **create a child** (`bd create --parent <id> --external-ref
  gh-<n>#<comment-id>`) for a new required correction.
- Don't duplicate work already in beads; beads is the sole record (CLAUDE.md §4).
  If the parent's merge already delivered part of this issue's scope, record it
  and reconcile acceptance before continuing — arbitrate (CLAUDE.md §7) if the
  issue is effectively absorbed.
- Then `bd update <id> --status in_progress`.

## Continue the issue (normal CLAUDE.md flow)
An ordinary issue run **in this worktree**. Re-read the issue's current body and
spec paths (may have moved since the branch was cut), then work per
CLAUDE.md/`AGENTS.md`. Only deltas:
- **Re-run acceptance locally after the rebase** — the merged parent may have
  moved shared code; a stale green doesn't count. Only once it passes again,
  `push --force-with-lease` (never push before) and update the bead's top note.
- Existing PR ⇒ update **its** body (base/head/verification); else open one PR to
  `main` with results and the attribution line. One branch = one PR.
- Close the bead only when acceptance is **verified**; never merge the PR, never
  edit/close the GitHub issue (CLAUDE.md / AGENTS.md).

## Cleanup when issues are done (CLAUDE.md §1, automatic)
Delete a worktree/branch **only when proven no longer useful** — content is
**duplicated on `main`** (merged PR) or **proven obsolete**. Proof is the gate;
without it, leave the branch alone.
- Proven redundant: `gh pr view <pr> --json state,mergedAt` shows MERGED, its
  issue is closed, and the branch adds nothing not on `main`
  (`git -C <dir> log --oneline origin/main..HEAD` empty, or only merged content).
  Only then:
  ```
  git worktree remove <dir>          # from another worktree; must be clean
  git branch -D <branch>             # -D: squash-merge leaves it "unmerged"
  git push origin --delete <branch>  # remote — only after redundancy is proven
  ```
- **Doubt ⇒ leave it.** Unmerged/open PR, open issue, non-empty
  `origin/main..HEAD`, ambiguous fork point, or anything not confirmed
  duplicated/obsolete ⇒ delete **nothing**, not even the remote branch. The
  remote branch is the harder to recover: delete it last, only on proof. A
  stale-but-harmless branch costs little; a wrongly deleted one is gone.
- **Never** delete the worktree/branch you are standing in (the owner does).
Cleanup only — still never merge a PR or close an issue yourself.

## Stop only if truly stuck
Unresolvable conflict; parent not actually merged (premise fails); ambiguous merge
boundary (wrong-base risk); worktree/branch mismatch; acceptance impossible with
available code/specs; missing secret/service; plan self-contradictory. Anything
else: assume, note it, continue. When you stop: branch pushed, bead note current,
state exactly what blocks and what would unblock it.

## Cheat sheet
```
gh pr list --state merged                            # confirm the parent merged
git worktree list                                    # find the existing worktree
git -C <dir> branch --show-current                    # confirm the branch
git -C <dir> fetch origin && git -C <dir> status --short
git -C <dir> log --oneline origin/main..HEAD          # this issue vs parent commits
git -C <dir> rebase --onto origin/main <base> HEAD    # drop the merged parent
grep -rn '<<<<<<<' <dir>                              # must be empty
git -C <dir> log --oneline origin/main..HEAD          # now only this issue
# ...sync beads (gh issue view <n> --comments), then continue; re-run acceptance
git -C <dir> push --force-with-lease origin <branch>  # ONLY after acceptance re-proven
bd show <id>; bd note <id> "..."; bd update <id> --status in_progress
bd update <id> --status closed                        # only when verified
# never: new worktree/branch | git merge main | git rebase --update-refs
#        | gh pr merge | gh issue edit/close | delete the current worktree/branch
#        | delete any branch without proven redundancy/obsolescence (doubt ⇒ keep)
```
