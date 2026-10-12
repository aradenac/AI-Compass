---
name: multi-issue-delivery
description: Deliver a queue of GitHub issues in one Claude Code instance - one issue = one worktree = one branch = one PR, in priority order, each branch stacked on the previous. Use for batch/queue requests ("work #123..#126"), "parallel across issues", or /multi-issue-delivery. Governs multi-issue runs; CLAUDE.md still governs each individual issue.
---

# Multi-issue delivery

CLAUDE.md governs how to do one issue; this skill governs doing several in
sequence. Read CLAUDE.md first — everything here that isn't restated still
follows it. Spec: `AGENTS.md`. Queue: `docs/future-evolutions/implementation-plan.md`.

## The rules
1. one issue = one worktree = one branch = one PR
2. priority order, one at a time: finish issue 1 through its PR, then issue 2
3. each branch starts from the previous issue's branch (so it includes that
   work), not from main
4. work alone: write your best guess as a bead note and keep going; stop only
   if truly stuck (see Stop)

## Before you start
- get the queue from implementation-plan.md; confirm against `gh issue list`
- each issue needs a bead with `--external-ref gh-<n>`, a `--design` doc, and a
  real `--acceptance`. No acceptance criteria = fix that first
- make one epic bead for the run and put the ordered queue in its note
- clean working tree

## Set up (when you reach each issue)
- worktree `../AI-Compass-agentN`; branch `agent/gh-<n>-<topic>-<date>`
- create it then, based on the previous issue's branch:
  `git worktree add <dir> -b <branch> <previous-branch>` (issue 1: base `main`)
- beads is shared across worktrees automatically — never copy `.beads/`

## Do the issue
1. `bd show <id>`; check the spec paths and acceptance still exist
2. `bd update <id> --status in_progress`
3. implement only this issue; keep AGENTS.md's invariants; reuse existing code
4. run the acceptance tests **locally** and make them pass here — do not push
   and wait for CI; CI is only the final check. Save the evidence
5. if unsure, write the assumption in a bead note and continue; never widen
   scope, never skip an acceptance criterion
6. commit; update the bead's top note (date, state, what's proven, what's left,
   next command)
7. push; open one PR to `main` for this issue, with the results and the
   attribution line
8. close the bead only when acceptance is actually verified

Never merge a PR or change a GitHub issue — that is the user's job.

## When a PR gets merged
Nothing merges while you work, so you normally never rebase. Only when a PR
*has* been merged (the user merged one, or you are cleaning up at the end),
update the branches above it, one worktree at a time, bottom-up:
```
git rebase --onto <parent-branch> <parent-branch> <child-branch>
```
Both arguments are the same branch; this drops the parent's now-merged commits.
Then re-run that issue's acceptance and `git push --force-with-lease`.
Check with `git -C <worktree> log --oneline main..HEAD` — it should show only
that issue's commits.
Do not use `--update-refs` (it fails here), and never `git merge main` into a branch.
(Until a parent merges, GitHub shows its stacked children with cumulative diffs —
that is expected.)

## Between issues
Before the next issue: reread the previous bead's notes for changes to shared
files, and update the epic note.

## GitHub issues: read only
Read them freely. Never edit, close, or comment unless the user asks. Review
comments get copied into beads, never answered on GitHub.

## Stop only if truly stuck
An unresolvable conflict; acceptance impossible with the available code/specs;
a missing secret, database, or service; the plan contradicting itself.
Anything else: assume, note it, continue. When you do stop: branches pushed,
notes current, and say exactly what is blocking and what would unblock it.

## Finished when
- every issue has its own worktree, branch, PR, and a closed bead
- the epic note lists each issue, its PR number, and its test evidence
- nothing was pushed to main, no GitHub issue changed, no PR merged by you
- a fresh session could resume from beads + git alone

## Cheat sheet
```
git worktree add ../AI-Compass-agent3 -b agent/gh-124-<topic>-<date> agent/gh-123-<topic>-<date>
git rebase --onto <parent> <parent> <child>        # only after a PR merged
git push --force-with-lease origin <branch>
bd show <id>; bd update <id> --status in_progress; bd note <id> "..."
gh pr create --base main --body "..."
bd update <id> --status closed
# never: git push origin main | gh pr merge | gh issue edit/close
```
