# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

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
