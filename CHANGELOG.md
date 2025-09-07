# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [0.2.0] - 2025-09-07

### Added
- Unified, tabbed GUI (`Logger` + `Awards`) launched via `w4gns_skcc_logger.py` (legacy mode still available with `--legacy`).
- Comprehensive specialty award support: Canadian Maple (Yellow/Orange/Red/Gold), DX (DXQ & DXC with QRP), PFX (Px1–Px10, Px15+), Triple Key (per-key + overall), Rag Chew (RC1–RC50 incl. band endorsements), and Worked All Continents (overall, band, QRP).
- Historical Tribune / Senator tracking using *actual suffix at QSO time* from ADIF SKCC field (accurate award progression timeline).
- Roster / ADIF session persistence (restores last ADIF files, roster mode, and logger ADIF path on restart).
- Previous QSO lookup panel showing most recent contact context beneath callsign entry.
- Space Weather panel integration (propagation context at a glance).
- Backup configuration persistence (`~/.skcc_awards/backup_config.json`).
- Cluster (RBN) integration refactor into reusable `ClusterController` component with improved SKCC membership tag merging and duplicate suppression.
- Enforce / relax award rule toggles in Awards tab: key type enforcement, missing key handling, suffix rule enforcement.

### Changed
- Award calculation engine (`backend/app/services/skcc.py`) substantially expanded with modular calculators for each specialty award; clearer dataclasses for result sets.
- Tribune/Senator logic rewritten to: (a) anchor Centurion timestamp, (b) count NEW post‑Centurion C/T/S uniques for Tribune & endorsements, (c) require Tx8 date + post‑20130801 T/S uniques for Senator path.
- Improved ADIF parsing: more robust SKCC field extraction (fallback to comment tag), key type detection, power/QRP heuristics.
- Cluster spot rendering now normalizes club list with SKCC precedence and trims to last 50 entries (newest first).
- Auto roster update now runs on startup with a 1‑hour freshness threshold (status & member count surfaced in UI).
- README overhauled to reflect unified GUI and expanded award coverage.

### Fixed
- Historical suffix handling to prevent inflating Tribune/Senator counts with current roster status.
- Multiple edge cases in call normalization (portable suffix chains, leading prefixes) enhancing award and membership matching.
- UI race conditions when adding/deleting Treeview rows under rapid cluster updates.

### Removed
- Deprecated standalone awards GUI launcher script usage in favor of unified tabbed interface (legacy retained only for fallback/testing).

---

## [0.1.0] - 2025-09-02

### Added
- Worked All Continents (WAC) award calculation, including QRP and band endorsements.
- Historical SKCC award logic that respects member status at QSO time for Tribune/Senator.
- Extensive test coverage for parsing, awards, key type rules, WAC, and edge cases.
- Lint configurations: `ruff.toml` and `.flake8`.
- New GUI forms and scripts to support workflows (e.g., roster QSO).

### Changed
- Cleaned backend services: fixed indentation, long lines, and exception handling in `backend/app/services/skcc.py`.
- Improved ADIF parsing and callsign normalization; more robust roster fetching with fallbacks.
- Enhanced award descriptions and endorsement progress details.

### Fixed
- Resolved VS Code Problems across the codebase (spacing, line length, unused variables).
- Narrowed overly broad exception handling.

---

[0.1.0]: https://github.com/garyPenhook/skcc_awards_calculator/releases/tag/v0.1.0
[0.2.0]: https://github.com/garyPenhook/skcc_awards_calculator/compare/v0.1.0...v0.2.0
