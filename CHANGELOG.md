# Changelog

## [Unreleased]

### Documentation - 2026-10-21

- Document user-operated Work Local / Codex Local window verification: 500K raw → 475K effective, 600K raw → 570K effective in both modes.
- Clarify shared local configuration, new-chat behavior, and all-model / selected-model scope without separate per-mode settings.
- Separate desktop window evidence from the earlier engine-level compaction tests; add manual reproduction steps and explicit limits.
- No runtime changes; the 0.4.0 tag and release assets remain unchanged.

## [0.4.0] - 2026-10-21

First public release.

- Add independent context-window, effective-percentage, and auto-compaction controls.
- Support all-model and selected-model settings, with explicit previews and transactional restore.
- Refresh from the local cache, a supplied catalog, or the installed Codex bundled catalog.
- Preserve recorded choices during refresh; migrate recorded 0.3.0 window choices.
- Stop on unknown catalog history, incompatible limits, or restore conflicts.
- Publish portable instructions, 33 isolated regression tests, validation scope, and release tooling.

Earlier versions were local development versions and were not published from this repository.
