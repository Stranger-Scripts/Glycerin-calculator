# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-08-05

### Added
- Temperature-aware density. Reference tables now exist at 15, 15.5, 20, 25 and
  30 °C. `density()` is bilinear — piecewise-linear in concentration, then linear
  in temperature between the two anchor tables bracketing the requested
  temperature. Temperatures outside 15–30 °C extrapolate from the nearest pair.
- Grid-integrity tests: every column is monotonic in concentration, density falls
  strictly with temperature at all concentrations, and each anchor reproduces its
  reference table at the pure-component ends.

### Changed
- `vv_to_ww()` / `ww_to_vv()` are temperature-aware: the pure glycerol and water
  densities are read from the reference tables at the given temperature instead of
  hard-coded 20 °C constants. (v/v stays the standard pre-mixing convention.)
- Temperature is threaded through every density lookup in `calculate()` and
  `calculate_batch()`.

### Fixed
- `pyproject.toml`: `[dependencies-groups]` → `[dependency-groups]` (PEP 735), so
  the dev dependency group (pytest, httpx) installs and the test suite runs.

### Notes
- Backward-compatible: `density()`, `vv_to_ww()` and `ww_to_vv()` keep their
  previous signatures via a `T=20.0` default, so all existing call sites and tests
  are unaffected.
