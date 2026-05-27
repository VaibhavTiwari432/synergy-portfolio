# Claude Code Phase 0 Handoff

Last updated: 2026-05-21

## Intent

Finish the Phase 0 calibration foundation described in `CLAUDE.md` and `SYNERGY_PORTFOLIO_SPEC.md` before any Phase 1 judge-service work begins.

## Accomplished

- Added `gc-005.json` through `gc-023.json` under `gold_standard/chats/`.
- Added `calibration/gold_standard_loader.ts`.
- Added `calibration/gold_standard_loader.test.ts`.
- Added `calibration/package.json` and `calibration/tsconfig.json`.
- Added `calibration` to `pnpm-workspace.yaml`.
- Updated `gold_standard/README.md` from stale `0 / 20` status to `23 / 20`.
- Changed empty future-phase package test scripts to `vitest run --passWithNoTests` so root `pnpm test` is not blocked by packages that intentionally have no tests yet.

## Current Phase 0 Checklist

- `packages/rubric/rubric_v0.1.json`: present.
- Rubric validation tests: present in `packages/rubric/src/loader.test.ts`.
- `packages/schemas`: present.
- Schema tests: present in `packages/schemas/src/index.test.ts`.
- Gold standard JSON count: 23 files.
- Gold standard loader: present.
- Loader tests: present.

## Known Caveat

Most `gc-*.json` files use placeholder transcript turns instead of full raw chat turns. They validate as `GoldChat` records, but true judge calibration will need the real conversation turns extracted into the `turns` arrays.

## Verification

Passed on 2026-05-21:

```powershell
pnpm test
pnpm --filter @synergy/calibration typecheck
pnpm --filter @synergy/calibration build
```

`pnpm typecheck` also passes across workspace packages.

## Next Recommended Step

Decide whether the placeholder transcript turns are acceptable for the first judge calibration run. If not, extract full conversation turns from the source PDFs/markdown files before starting Phase 1.
