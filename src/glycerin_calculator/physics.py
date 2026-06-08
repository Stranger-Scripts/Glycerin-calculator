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

from glycerin_calculator.density_data import _DENS_TABLE_20C

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


def density(mass_frac: float) -> float:
    """Density of a glycerol–water mixture in g/mL given mass fraction (0–1)."""
    p = max(0.0, min(100.0, mass_frac * 100))
    for i in range(len(_DENS_TABLE_20C) - 1):
        x0, y0 = _DENS_TABLE_20C[i]
        x1, y1 = _DENS_TABLE_20C[i + 1]
        if x0 <= p <= x1:
            return y0 + (y1 - y0) * (p - x0) / (x1 - x0)
    return _DENS_TABLE_20C[-1][1]


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------

def vv_to_ww(v_frac: float) -> float:
    """Convert glycerol volume fraction to mass fraction (uses pure-component densities)."""
    rho_g, rho_w = 1.26108, 0.99823
    mass_g = v_frac * rho_g
    mass_w = (1 - v_frac) * rho_w
    return mass_g / (mass_g + mass_w)


def ww_to_vv(w_frac: float) -> float:
    """Convert glycerol mass fraction to volume fraction."""
    rho_g, rho_w = 1.26108, 0.99823
    vol_g = w_frac / rho_g
    vol_w = (1 - w_frac) / rho_w
    return vol_g / (vol_g + vol_w)


# ---------------------------------------------------------------------------
# Main calculation
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CalcResult:
    # inputs echoed back
    target_mu: float
    T: float
    V0: float
    w0: float           # current glycerol mass frac
    ws: float           # stock glycerol mass frac
    stock_pct: float
    basis: str

    # outputs
    wf: float           # required final glycerol mass frac
    wf_vv: float        # same, as volume fraction
    base_mu: float      # viscosity of current solution
    Vs: float           # stock volume to add (mL)
    final_vol: float    # final solution volume (mL)

    error: str | None = None
    mode: str = "solve"  # "solve" (dose from target) or "forward" (η from dose)


def calculate(
    target_mu: float,
    T: float,
    V0: float,
    w0_pct: float,
    stock_pct: float,
    basis: Literal["ww", "vv"],
) -> CalcResult:
    """
    Compute how many mL of stock to add to reach *target_mu*.

    Parameters
    ----------
    target_mu : float   Target viscosity in mPa·s
    T         : float   Temperature in °C
    V0        : float   Current solution volume in mL
    w0_pct    : float   Glycerol already in solution, in % (w/w)
    stock_pct : float   Stock glycerol concentration in %
    basis     : str     "ww" or "vv" — applies to stock_pct
    """
    w0 = w0_pct / 100
    ws = stock_pct / 100 if basis == "ww" else vv_to_ww(stock_pct / 100)

    sol = solve_cm(target_mu, T)
    wf = sol.cm
    base_mu = mix_visc(w0, T)

    error: str | None = None
    if sol.status == "high":
        error = "Target exceeds pure glycerol viscosity at this temperature — unreachable."
    elif wf <= w0 + 1e-6:
        error = (
            "Target viscosity is at or below your current solution. "
            "Adding glycerin only raises it."
        )
    elif wf >= ws - 1e-6:
        error = (
            f"Your {stock_pct:.0f}% stock is too dilute — you would need "
            f"≥ {wf * 100:.1f}% glycerol. Use a stronger stock."
        )

    m0 = V0 * density(w0)
    ms = m0 * (wf - w0) / (ws - wf) if not error else 0.0
    Vs = ms / density(ws) if not error else 0.0
    final_mass = m0 + ms
    final_vol = final_mass / density(wf) if not error else V0

    return CalcResult(
        target_mu=target_mu, T=T, V0=V0, w0=w0, ws=ws,
        stock_pct=stock_pct, basis=basis,
        wf=wf, wf_vv=ww_to_vv(wf),
        base_mu=base_mu, Vs=Vs, final_vol=final_vol,
        error=error, mode="solve",
    )


def calculate_forward(
    Vs: float,
    T: float,
    V0: float,
    w0_pct: float,
    stock_pct: float,
    basis: Literal["ww", "vv"],
) -> CalcResult:
    """
    Forward calculation: given a fixed stock volume to add, report the
    resulting viscosity. Parameters mirror :func:`calculate`, except *Vs*
    (the stock volume to add, in mL) replaces *target_mu* as the input.
    """
    w0 = w0_pct / 100
    ws = stock_pct / 100 if basis == "ww" else vv_to_ww(stock_pct / 100)
    base_mu = mix_visc(w0, T)

    m0 = V0 * density(w0)
    ms = Vs * density(ws)
    final_mass = m0 + ms

    error: str | None = None
    if Vs < 0:
        error = "Stock volume to add cannot be negative."
    elif final_mass <= 0:
        error = "Enter a non-zero current or stock volume."

    if error:
        wf, result_mu, final_vol = w0, base_mu, V0
    else:
        wf = (m0 * w0 + ms * ws) / final_mass
        result_mu = mix_visc(wf, T)
        final_vol = final_mass / density(wf)

    return CalcResult(
        target_mu=result_mu, T=T, V0=V0, w0=w0, ws=ws,
        stock_pct=stock_pct, basis=basis,
        wf=wf, wf_vv=ww_to_vv(wf),
        base_mu=base_mu, Vs=Vs, final_vol=final_vol,
        error=error, mode="forward",
    )


def viscosity_curve(T: float, n_points: int = 51) -> list[dict[str, float]]:
    """Return [{pct, mu}, ...] for the viscosity–concentration curve at T °C."""
    return [
        {"pct": p, "mu": mix_visc(p / 100, T)}
        for p in [i * 100 / (n_points - 1) for i in range(n_points)]
    ]
