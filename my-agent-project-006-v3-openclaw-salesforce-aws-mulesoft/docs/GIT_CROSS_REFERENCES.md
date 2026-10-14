# Git Cross-References — 006 V3 branch

## Commits on this branch that look out-of-place

### `cf1721d4 docs(007/trust): progress report for remediation-trust-fixes`

**Where it lives:** `feat/006-v3-live-demo` between `1e32fd0b` (FULL VAULT) and `14367edf` (Narrative 2 backend).

**Why it's here:** the commit's own message explains it — the workspace branch "repeatedly switched between `feat/007-phase4-m11-wave4` and `feat/006-v3-live-demo` between tool calls, silently reverting uncommitted edits." The progress-report markdown for the 007 trust remediation was written during a session where the builder was on the v3 branch, and committing it to the v3 branch preserved the file rather than losing it to a branch switch.

**What it contains:** only one file — `my-agent-project-007-fsi-interoperability/specs/remediation-trust-fixes-PROGRESS.md` (127 lines). Zero v3 content. Zero v3 code changes. Pure documentation.

**Why we leave it:** history rewrite is high-risk and this commit is harmless — it's one markdown file that happens to live on the "wrong" branch but doesn't conflict with anything, doesn't affect v3 code, and doesn't affect 007 code. Rewriting history to move it to `feat/007-phase4-m11-wave4` would require a force-push, which breaks anyone else's clone.

**If someone finds this later:** the 007 trust progress report legitimately belongs on the 007 branch. The content is also available on 007 work stashes (`stash@{6}` for example). The copy on the v3 branch is effectively a cross-listed reference.

---

## Stashes worth knowing about

See `/tmp/stash-audit/stash-*.patch` for the full content of each stash. Summary:

| Stash | Branch it was made on | Contains |
|---|---|---|
| stash@{0-1} | 007 | WIP overlap with origin/feat/007 |
| stash@{2} | 007 | tiny .pyc only |
| stash@{3} | 006-v3 | liaison_orchestrator + rm_handoff early draft — **superseded by commit `cfbb50ec`** |
| stash@{4} | 007 | WIP during v3 deploy session |
| stash@{5} | 006-v3 | research_orchestrator + tool_dispatch + topology edits — **may contain unique content, needs review** |
| stash@{6} | 007 | tenant_id work on m1_identity |
| stash@{7} | 007 | mulesoft poms + tool_dispatch — **may contain unique content** |
| stash@{8} | 007 | WIP with gap4 |
| stash@{9} | 006-v3 | mulesoft-actions/app.py + 007 MNPI — **may contain unique content** |

Stashes marked "superseded" are safe to drop after confirmation.
Stashes marked "needs review" should be diffed against current HEAD before dropping.
Stashes on 007 branch should be reviewed while checked out to 007 branch.

---

## Safety tags

Before any cleanup, these three tags were created and pushed:

- `archive/pre-cleanup/feat-006-v3-live-demo` → commit `cfbb50ec` (pre-commit-B4DB3817 state)
- `archive/pre-cleanup/feat-007-phase4-m11-wave4` → commit `caf748e5`
- `archive/pre-cleanup/main` → commit `cd92b1ad`

Any recovery can start from these tags.
