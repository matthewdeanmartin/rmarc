---
name: kaclm-release-recovery
description: Recover failed GitHub releases managed by keepachangelog-manager-fork (kaclm), restore unreleased development state, and validate changelog links.
---

# Recover a kaclm GitHub release

Inspect repository instructions, working-tree changes, release workflows, and the installed `kaclm --help` before choosing commands. Use the project's environment and Makefile; in this Windows workspace use Git Bash and `.venv/Scripts/python.exe -m changelogmanager` when direct CLI execution is needed.

## Establish the recovery target

- Fetch/pull without overwriting user changes. Identify the exact failed tag, release ID, bump commit, pre-bump versions, workflow failure, and any later fixes.
- Read GitHub release/run state and the package index. A deleted GitHub release does not unpublish PyPI files. If the version was uploaded, plan a new version instead of assuming it can be reused.
- Check remote tags separately: `git fetch` does not remove stale local tags. Do not invent historical tags just to silence link warnings.
- Existing authorization to recover the identified failed release covers its cleanup. Do not infer authorization to publish a replacement or delete unrelated releases.

## Recover only the failed attempt

Installed 6.10.1 supports:

```bash
kaclm release-rollback --tag vX.Y.Z --repository owner/repo --dry-run
kaclm release-rollback --tag vX.Y.Z --repository owner/repo --yes
```


Inspect current help for selective `--no-github`, `--no-local-tag`, and `--no-remote-tag` switches. This version deletes release/tag artifacts only: it does not undo version bumps or restore changelog sections. Verify remote outcomes independently; its implementation can report a failed tag deletion as an already-missing tag.

Restore version fields from the actual bump's parent, including lockfiles only if changed. Preserve later functional fixes and unrelated edits. Move the failed release's entries back into Unreleased, merging with any newer entries without duplication; preserve historical releases. If someone already restored Unreleased, finish that recovery rather than reverting the whole changelog. Prefer a forward recovery commit to rewriting shared history.

Repair comparison references using existing tags or historically justified commit hashes. For an initial release with no predecessor use its source tree/commit URL, not a self-comparison. Ensure Unreleased compares the last release baseline to HEAD. Run `kaclm validate --strict`; inspect diffs after any `validate --fix`, since generated tag links may reference nonexistent tags.

Keep `release-bump` output outside the checkout, e.g. `$RUNNER_TEMP/release-bump.json`: shell redirection creates an untracked file before the clean-tree check. Global `--json` goes before the subcommand. Check synchronized package/lock versions and workflow syntax. Commit/push when requested, then verify the remote commit and resulting checks. A push may automatically create a new draft release; do not publish it without authorization.

For tooling improvements, read [the proposed recovery extension](references/recovery-extension.md). These options are a design proposal, not commands available in 6.10.1.
