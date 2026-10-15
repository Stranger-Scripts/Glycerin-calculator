# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-15

### Added
- Each concentration carries its own basis picker. `w0_basis` labels the base
  solution, `stock_basis` labels the stock bottle, and the two are independent —
  a manufacturer prints whichever convention they like, and the base solution's
  provenance has nothing to do with it.
- `measure` ("mass" | "volume") selects the bench units, independently of both
  labels. Whichever quantity you measure is treated as exact and the other is
  derived from density, so weighing closes the mass balance exactly while
  dispensing by volume leaves the components summing to slightly more than the
  final volume.
- `as_mass_frac(pct, basis, T)` — reads a percentage in its own basis as a mass
  fraction, so the three settings never have to be resolved against each other.
- `CalcResult.ws_vv`, and a "stock strength" row in the result panel echoing the
  stock in both conventions ("86% w/w ≡ 81.9% v/v"). A bare percentage names a
  different liquid under each convention, which was the one genuinely confusing
  thing about the old single toggle.
- Tests for the three settings as independent axes: the bases do not interfere,
  `measure` never touches the concentrations, all four label combinations are
  distinct, the same physical stock gives the same answer however it is
  labelled, and all eight combinations hit the target viscosity.
- `data/density_table.csv` — the reference table the anchors in `density_data.py`
  were transcribed from. Kept for provenance; not read at runtime.

### Changed
- **Breaking.** `calculate(V0=, basis=)` → `calculate(amount0=, w0_basis=,
  stock_basis=, measure=)`, and `calculate_batch(V_final=, basis=)` →
  `calculate_batch(amount_final=, w0_basis=, stock_basis=, measure=)`. The
  amount parameters are no longer volumes by definition — `measure` decides.
- **Breaking.** Form fields `volume` / `final_volume` → `amount` /
  `final_amount`; `basis` → `w0_basis`, `stock_basis`, `measure`. The three new
  basis fields default so an older form body still posts successfully, but
  `volume` does not.
- Dilute-stock errors quote the shortfall in the stock's own label rather than
  always in w/w.
- UI copy is unit-neutral where it has to be: "Current volume" / "Final volume"
  → "Current amount" / "Final amount", relabelled to mass or volume by the
  measure toggle.
- Dependencies: fastapi >=0.143.2, uvicorn >=0.54, plotly >=7.1.0.

### Notes
- The old `basis` toggle conflated three unrelated things — the base's label,
  the stock's label, and the units you dispense in. Flipping it changed the
  meaning of every number on the form at once, which made two correct results
  look contradictory. They are now orthogonal, and nothing about a label
  affects how much you weigh out.
- Switching `measure` reinterprets the amount field rather than converting it:
  `1000` means 1000 g under Weight and 1000 mL under Volume. Those differ by the
  density of the base, so the recipe scales accordingly — this is intended, not
  rounding drift.

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
