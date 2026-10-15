"""
glycerin_calculator.physics
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Cheng (2008) glycerol–water viscosity model, density table, and unit
conversion helpers.  All concentrations are mass fractions (0–1) unless
the function name says otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from glycerin_calculator.density_data import _DENS_ANCHORS

# ---------------------------------------------------------------------------
# Viscosity model (Cheng 2008)
# ---------------------------------------------------------------------------

def _water_visc(T: float) -> float:
    """Dynamic viscosity of pure water in mPa·s at T °C."""
    return 1.79 * math.exp(((-1230 - T) * T) / (36100 + 360 * T))


def _glyc_visc(T: float) -> float:
    """Dynamic viscosity of pure glycerol in mPa·s at T °C."""
    return 12100 * math.exp(((-1233 + T) * T) / (9900 + 70 * T))


def mix_visc(cm: float, T: float) -> float:
    """
    Dynamic viscosity of a glycerol–water mixture in mPa·s.

    Parameters
    ----------
    cm : float
        Glycerol mass fraction (0–1).
    T : float
        Temperature in °C.
    """
    a = 0.705 - 0.0017 * T
    b = (4.9 + 0.036 * T) * a**2.5
    alpha = 1 - cm + (a * b * cm * (1 - cm)) / (a * cm + b * (1 - cm))
    return _water_visc(T) ** alpha * _glyc_visc(T) ** (1 - alpha)


SolveStatus = Literal["ok", "low", "high"]


@dataclass(slots=True)
class SolveResult:
    cm: float          # required glycerol mass fraction
    status: SolveStatus


def solve_cm(target_mu: float, T: float) -> SolveResult:
    """
    Bisect for the glycerol mass fraction that yields *target_mu* at *T* °C.
    Returns status="low"/"high" when the target lies outside the model range.
    """
    lo_mu = mix_visc(0.0, T)
    hi_mu = mix_visc(1.0, T)
    if target_mu <= lo_mu:
        return SolveResult(cm=0.0, status="low")
    if target_mu >= hi_mu:
        return SolveResult(cm=1.0, status="high")
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if mix_visc(mid, T) < target_mu:
            lo = mid
        else:
            hi = mid
    return SolveResult(cm=(lo + hi) / 2, status="ok")


def _interp_conc(table: list[tuple[float, float]], p: float) -> float:
    """Piecewise-linear density lookup on *table* at concentration *p* (% w/w, 0–100)."""
    for i in range(len(table) - 1):
        x0, y0 = table[i]
        x1, y1 = table[i + 1]
        if x0 <= p <= x1:
            return y0 + (y1 - y0) * (p - x0) / (x1 - x0)
    return table[-1][1]


def density(mass_frac: float, T: float = 20.0) -> float:
    """
    Density of a glycerol–water mixture in g/mL.

    Bilinear over the reference grid: piecewise-linear in concentration, then
    linear in temperature between the two anchor tables bracketing *T*.

    Parameters
    ----------
    mass_frac : float
        Glycerol mass fraction (0–1).
    T : float
        Temperature in °C.  Anchors exist at 15, 15.5, 20, 25 and 30 °C, so
        the whole span is interpolated; temperatures outside [15, 30] are
        linearly extrapolated from the nearest anchor pair.
    """
    p = max(0.0, min(100.0, mass_frac * 100))

    # Pick the anchor pair bracketing T; clamp the index so temperatures below
    # the first / above the last anchor extrapolate from the end pair.
    i = 0
    while i < len(_DENS_ANCHORS) - 2 and T > _DENS_ANCHORS[i + 1][0]:
        i += 1
    t0, tbl0 = _DENS_ANCHORS[i]
    t1, tbl1 = _DENS_ANCHORS[i + 1]

    d0 = _interp_conc(tbl0, p)
    d1 = _interp_conc(tbl1, p)
    return d0 + (d1 - d0) * (T - t0) / (t1 - t0)


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------

def vv_to_ww(v_frac: float, T: float = 20.0) -> float:
    """
    Convert glycerol volume fraction to mass fraction at *T* °C.

    Uses the pre-mixing (standard) v/v convention: pure-component densities are
    taken at *T* from the reference tables so the conversion tracks temperature.
    """
    rho_g, rho_w = density(1.0, T), density(0.0, T)
    mass_g = v_frac * rho_g
    mass_w = (1 - v_frac) * rho_w
    return mass_g / (mass_g + mass_w)


def ww_to_vv(w_frac: float, T: float = 20.0) -> float:
    """Convert glycerol mass fraction to volume fraction at *T* °C (pre-mixing convention)."""
    rho_g, rho_w = density(1.0, T), density(0.0, T)
    vol_g = w_frac / rho_g
    vol_w = (1 - w_frac) / rho_w
    return vol_g / (vol_g + vol_w)


# ---------------------------------------------------------------------------
# Main calculation
# ---------------------------------------------------------------------------

# How a concentration percentage is labelled.  This is a property of the liquid
# in front of you — whichever convention the manufacturer printed on the bottle —
# so each concentration carries its own, independently of the others.
Basis = Literal["ww", "vv"]

# How you dispense at the bench.  Independent of any label: you can weigh out a
# stock that is specified v/v, or pipette one specified w/w.
Measure = Literal["mass", "volume"]


@dataclass(slots=True)
class CalcResult:
    # inputs echoed back
    target_mu: float
    T: float
    w0: float           # current glycerol mass frac
    w0_vv: float        # same, as volume fraction
    w0_pct: float
    w0_basis: str
    ws: float           # stock glycerol mass frac
    ws_vv: float        # same, as volume fraction
    stock_pct: float
    stock_basis: str
    measure: str

    # outputs
    wf: float           # required final glycerol mass frac
    wf_vv: float        # same, as volume fraction
    base_mu: float      # viscosity of current solution

    # Every amount is carried as both mass and volume so the view can present
    # whichever `measure` calls for.  In "solve" mode the base amount is the
    # input and the final amount is derived; in "batch" mode it is reversed.
    m0: float           # base/current solution mass (g)
    V0: float           # base/current solution volume (mL)
    ms: float           # stock mass to add (g)
    Vs: float           # stock volume to add (mL)
    final_mass: float   # final solution mass (g)
    final_vol: float    # final solution volume (mL)

    error: str | None = None
    mode: str = "solve"  # "solve" (dose from what you have) or "batch" (split a final amount)


def as_mass_frac(pct: float, basis: Basis, T: float = 20.0) -> float:
    """Read a concentration percentage labelled in *basis* as a mass fraction."""
    return pct / 100 if basis == "ww" else vv_to_ww(pct / 100, T)


def _balance_error(
    sol: SolveResult,
    w0: float,
    ws: float,
    stock_pct: float,
    stock_basis: Basis,
    T: float,
    base_label: str,
) -> str | None:
    """Reason the requested target cannot be reached by dilution, or None."""
    wf = sol.cm
    if sol.status == "high":
        return "Target exceeds pure glycerol viscosity at this temperature — unreachable."
    if wf <= w0 + 1e-6:
        return (
            f"Target viscosity is at or below your {base_label}. "
            "Adding glycerin only raises it."
        )
    if wf >= ws - 1e-6:
        # Quote the shortfall the way the stock is labelled, so it compares
        # directly against the figure on the bottle.
        need_pct = wf * 100 if stock_basis == "ww" else ww_to_vv(wf, T) * 100
        unit = "w/w" if stock_basis == "ww" else "v/v"
        return (
            f"Your {stock_pct:.0f}% stock is too dilute — you would need "
            f"≥ {need_pct:.1f}% ({unit}) glycerol. Use a stronger stock."
        )
    return None


def calculate(
    target_mu: float,
    T: float,
    amount0: float,
    w0_pct: float,
    stock_pct: float,
    w0_basis: Basis = "ww",
    stock_basis: Basis = "ww",
    measure: Measure = "mass",
) -> CalcResult:
    """
    Compute how much stock to add to reach *target_mu*.

    Parameters
    ----------
    target_mu   : float  Target viscosity in mPa·s
    T           : float  Temperature in °C
    amount0     : float  How much solution you already have — grams when
                         *measure* is "mass", millilitres when it is "volume"
    w0_pct      : float  Glycerol already in solution, in % of *w0_basis*
    stock_pct   : float  Stock glycerol concentration, in % of *stock_basis*
    w0_basis    : str    "ww" or "vv" — how the base solution is labelled
    stock_basis : str    "ww" or "vv" — how the stock bottle is labelled
    measure     : str    "mass" or "volume" — how you dispense at the bench

    The two bases are independent of each other and of *measure*: a stock
    specified v/v can be weighed out, and a base known w/w can be pipetted.
    """
    w0 = as_mass_frac(w0_pct, w0_basis, T)
    ws = as_mass_frac(stock_pct, stock_basis, T)

    sol = solve_cm(target_mu, T)
    wf = sol.cm
    base_mu = mix_visc(w0, T)
    error = _balance_error(sol, w0, ws, stock_pct, stock_basis, T, "current solution")

    # Whichever way you measure is the exact input; the other is derived.
    if measure == "mass":
        m0 = amount0
        V0 = m0 / density(w0, T)
    else:
        V0 = amount0
        m0 = V0 * density(w0, T)

    ms = m0 * (wf - w0) / (ws - wf) if not error else 0.0
    Vs = ms / density(ws, T) if not error else 0.0
    final_mass = m0 + ms
    final_vol = final_mass / density(wf, T) if not error else V0

    return CalcResult(
        target_mu=target_mu, T=T,
        w0=w0, w0_vv=ww_to_vv(w0, T), w0_pct=w0_pct, w0_basis=w0_basis,
        ws=ws, ws_vv=ww_to_vv(ws, T), stock_pct=stock_pct, stock_basis=stock_basis,
        measure=measure,
        wf=wf, wf_vv=ww_to_vv(wf, T), base_mu=base_mu,
        m0=m0, V0=V0, ms=ms, Vs=Vs,
        final_mass=final_mass, final_vol=final_vol,
        error=error, mode="solve",
    )


def calculate_batch(
    target_mu: float,
    T: float,
    amount_final: float,
    w0_pct: float,
    stock_pct: float,
    w0_basis: Basis = "ww",
    stock_basis: Basis = "ww",
    measure: Measure = "mass",
) -> CalcResult:
    """
    Compute the base-solution and stock amounts to combine to make exactly
    *amount_final* of final solution at *target_mu*.

    Same mass balance as :func:`calculate`, but the desired final amount is the
    input and both components (base and stock) are solved for.

    Parameters
    ----------
    amount_final : float
        Finished solution wanted — grams when *measure* is "mass", millilitres
        when it is "volume".  Measuring by volume, note that glycerol–water
        mixing contracts, so ``V0 + Vs`` exceeds ``final_vol`` slightly; the
        balance is exact by mass either way.

    The remaining parameters carry the same meaning as in :func:`calculate`.
    """
    w0 = as_mass_frac(w0_pct, w0_basis, T)
    ws = as_mass_frac(stock_pct, stock_basis, T)

    sol = solve_cm(target_mu, T)
    wf = sol.cm
    base_mu = mix_visc(w0, T)
    error = _balance_error(sol, w0, ws, stock_pct, stock_basis, T, "base solution")

    if error:
        # Nothing downstream is meaningful; the view renders only the message.
        final_mass = amount_final if measure == "mass" else 0.0
        final_vol = amount_final if measure == "volume" else 0.0
        ms = m0 = Vs = V0 = 0.0
    else:
        if measure == "mass":
            final_mass = amount_final
            final_vol = final_mass / density(wf, T)
        else:
            final_vol = amount_final
            final_mass = final_vol * density(wf, T)
        ms = final_mass * (wf - w0) / (ws - w0)
        m0 = final_mass - ms
        Vs = ms / density(ws, T)
        V0 = m0 / density(w0, T)

    return CalcResult(
        target_mu=target_mu, T=T,
        w0=w0, w0_vv=ww_to_vv(w0, T), w0_pct=w0_pct, w0_basis=w0_basis,
        ws=ws, ws_vv=ww_to_vv(ws, T), stock_pct=stock_pct, stock_basis=stock_basis,
        measure=measure,
        wf=wf, wf_vv=ww_to_vv(wf, T), base_mu=base_mu,
        m0=m0, V0=V0, ms=ms, Vs=Vs,
        final_mass=final_mass, final_vol=final_vol,
        error=error, mode="batch",
    )


def viscosity_curve(T: float, n_points: int = 51) -> list[dict[str, float]]:
    """Return [{pct, mu}, ...] for the viscosity–concentration curve at T °C."""
    return [
        {"pct": p, "mu": mix_visc(p / 100, T)}
        for p in [i * 100 / (n_points - 1) for i in range(n_points)]
    ]
