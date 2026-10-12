# AI Compass — agent rules (beads tracking)

For the agent. Complements `AGENTS.md` (authoritative on *what* to build:
scope, invariants, acceptance). This file governs *how* to track work.
Applies to every task in this project, not to any one in-flight effort.
On resuming (new session, after compaction), re-ground on beads + git — not on
chat history: see §8.

## 1. Track all work in beads
- Use beads (`bd`) as the sole tracker; store in `.beads/`, shared across sessions.
- Invoke `bd` directly. No symlinks, no wrappers.
- Read before work: `bd show <id>`. One issue = one coherent unit; don't fragment,
  don't silently widen.
- Group issues under an epic when they form one effort; link with `bd link`/`--deps`;
  no orphan issues.
- **One GitHub issue = one branch = one PR.** Name the branch after the GitHub
  issue it serves (e.g. `agent/gh-123-<topic>-<date>`). Do the work on that branch
  and open **one PR per GitHub issue** once its scope is done. Don't mix unrelated
  issues in one branch/PR.
- **Clean up when the issue is done.** Once the PR is merged and the GitHub issue
  closed (or the issue is closed without a PR), delete the worktree and **both**
  the local and the remote branch — no stale worktrees or branches linger.

  ```bash
  git worktree remove <dir>            # run from another worktree; must be clean
  git branch -D <branch>               # local; -D because squash-merge leaves it "unmerged"
  git push origin --delete <branch>    # remote
  ```

  Never delete the worktree/branch you are currently on (the owner deletes the
  branch if you are standing in it). This is cleanup, not a merge or a close — the
  agent still never merges PRs nor closes issues (AGENTS.md).

## 2. Every issue references its GitHub issue + governing spec
At creation, each issue MUST carry:
- **GitHub issue**: `--external-ref gh-<n>`; name the owning PR in the body if any.
- **Spec, by path**, in `--design`. Cite only existing docs; re-verify path/line
  before relying. Canonical sources:
  - `docs/product-definition.md`, `docs/benchmark-workflow.md` (semantics)
  - `docs/platform-architecture-and-data-governance.md` (persistence/evidence/migration)
  - `docs/future-evolutions/implementation-plan.md` (live roadmap/deps)
  - `docs/features/README.md` (delivered specs)
  - `docs/technical-debt.md` (debt ledger)
  - plus the domain-specific doc for the area touched, if one exists
- **DoD + precise verification** in `--acceptance`: exact commands/tests, the
  observable result proving each criterion, and the artifact evidencing it
  (test name, screenshot path, HTTP status). Checkable, reproducible, not a
  restatement of the goal. No DoD ⇒ not ready to start.

## 3. Update as you work; leave a periodic status
Record state continuously so any session resumes from the issue alone. Append:
- **Progress/logs** — done + proving artifact (SHA, file:line, test, screenshot).
- **Decisions** — choice + reason (don't re-litigate).
- **Problems** — blocker/failure/surprise + resolution or unblock status.
- **Arbitrations** — trade-off, option chosen, why.

`bd note <id> "…"` (append-only alias of `update --append-notes`) for running
notes; `bd comment <id>` for discrete entries. Read back: `bd show <id>` /
`bd comments <id>`. Append-only — never rewrite; add a new entry.
State: `bd update <id> --status …`. `closed` only when acceptance is *verified*;
`reopen` if untrue. A beads close ≠ authority to merge or close the referenced
GitHub issue — the agent never merges and never closes issues (AGENTS.md).

**Checkpoint** (commit, acceptance run, blocker, session end): keep the issue's
**top note = current state** (date, state, proven, remaining, next command),
history appended below it. Update it *before you stop*, not on a schedule —
always before a long/irreversible operation. Fresh-accurate > stale-complete.

## 4. On review, mirror GitHub comments into beads; never re-do handled ones
- When a PR is under review: read its GitHub review comments (`gh pr view <n> --comments`, `gh api repos/{owner}/{repo}/pulls/<n>/comments`), then update beads so it reflects the remaining work: **reopen** closed issues whose fix is challenged, add notes/comments, and **create child issues** (`bd create --parent <id>`) for new required corrections. Link each to its source comment (`--external-ref gh-<n>#<comment-id>` or the comment URL) so its origin is recoverable.
- A review comment already represented in beads MUST NOT be handled twice. Beads is the *sole* record of review work: before acting on a comment, match it against the open issues and their notes; if it is already tracked, neither duplicate it nor re-apply the fix — proceed via that issue.
- The backlog must represent exactly the remaining review work: nothing missing, nothing already done.

## 5. Prioritize per a plan agreed with the user
- Ordering is agreed with the user, not self-assigned. Encode: `bd priority <id> <n>`
  (0 critical … 4 backlog) + `bd link`/`--deps`.
- The current order is defined in `AGENTS.md` and the live implementation ledger —
  read it there; don't hardcode an order here. Never start a later/lower issue
  before an earlier approved one is accepted, regardless of issue numbers.
- No re-ordering without new user agreement. On change (blocker/evidence/decision),
  note the new order + reason on affected issues first.

## 6. Consult the backlog regularly; converge on the final solution
- Backlog = working memory of intent. Consult at session start, before picking
  next task, after each checkpoint (`bd ready`, `bd list --status open`,
  `bd show <id>`). Don't rely on chat history/recollection.
- Every action must advance the final agreed solution (the owning issue's
  acceptance + spec), not just a locally green test. Re-read DoD + verification
  before claiming progress.
- On divergence (finding contradicts issue, issue stale, acceptance ambiguous):
  stop, record a note, reconcile the issue first.

## 7. On any doubt, prompt the user for arbitration
- Any uncertainty that could change the outcome — ambiguous scope, conflicting
  specs, real trade-offs, flaky/nondeterministic result, data-loss/invariant
  risk, decision not covered by the plan — MUST prompt the user. Don't guess,
  don't default silently, don't widen scope.
- Give options + trade-offs + recommendation; wait. Record the outcome as a note (§3).
- Distinct from a **status** request: status ⇒ report from beads/GitHub and
  **stop**; don't ask for arbitration or resume work.

## 8. Resuming a long task (surviving context loss / compaction)
- **The ledger is a claim, not the truth** — verify it against reality before
  acting (`git log --oneline origin..HEAD`, `git status`); a stale note is worse
  than none because it's believed.
- **Update an issue's top note before you stop** (see §3), so a fresh session
  resumes from the issue alone.
- **Anything needed to resume lives in the repo** — never a scratch/profile path.
  What isn't in the repo doesn't exist for the next session.
- On resume: re-ground on the ledger + git, not on a summary of the conversation.

## Quick reference
```bash
bd ready                    # unblocked, next
bd list --status open       # open work
bd show <id>                # full detail incl. notes/comments
bd note <id> "2026-10-12: <progress/decision/problem/trade-off>"
bd comment <id>             # discrete entry
bd update <id> --status in_progress
bd priority <id> 1
bd reopen <id>                                   # review challenges a closed fix (§4)
bd create <child> -t task --parent <epic-id>     # new required correction (§4)
gh pr view <n> --comments                        # read PR review comments (§4)
gh api repos/{owner}/{repo}/pulls/<n>/comments   # line-level review comments (§4)
git worktree remove <dir>                        # cleanup once PR merged + issue closed (§1)
git branch -D <branch>                           #   local (squash-merge -> need -D)
git push origin --delete <branch>                #   remote
```
