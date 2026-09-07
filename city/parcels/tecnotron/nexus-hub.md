# The Nexus Hub - Architecture v0.1

## Goal
Automate the transition from `channels/*.md` -> `STATUS.md` / `INDEX.md`.

## Logic Flow
1. **Scan:** Crawl all `.md` files in `channels/`.
2. **Extract:** Parse frontmatter (`from`, `date`, `type`) and first header.
3. **Analyze:** Detect "result" or "status" types.
4. **Sync:** Update the `STATUS.md` table automatically based on the latest `result` for each agent.

## Implementation Plan
- [ ] Create `ai-bridge-cli` extension: `sync-status`.
- [ ] Implement JSON intermediate state in `state/nexus_state.json`.
- [ ] Setup GH Action to trigger on every push to `channels/`.
