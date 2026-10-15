"""Tests for glycerin_calculator."""

import math
import pytest
from fastapi.testclient import TestClient

from glycerin_calculator.main import app
from glycerin_calculator.physics import (
    mix_visc, solve_cm, density, vv_to_ww, ww_to_vv, calculate, calculate_batch,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------

class TestMixVisc:
    def test_pure_water_at_20(self):
        mu = mix_visc(0.0, 20)
        assert 0.9 < mu < 1.1  # ~1.002 mPa·s

    def test_pure_glycerol_at_20(self):
        mu = mix_visc(1.0, 20)
        assert mu > 1000  # ~1412 mPa·s

    def test_monotone_increasing(self):
        T = 20
        vals = [mix_visc(c, T) for c in [0, 0.25, 0.5, 0.75, 1.0]]
        assert all(vals[i] < vals[i+1] for i in range(len(vals)-1))

    def test_viscosity_drops_with_temperature(self):
        assert mix_visc(0.5, 40) < mix_visc(0.5, 20)


class TestSolveCm:
    def test_roundtrip(self):
        cm_target = 0.6
        mu = mix_visc(cm_target, 20)
        result = solve_cm(mu, 20)
        assert result.status == "ok"
        assert abs(result.cm - cm_target) < 1e-5

    def test_status_low_below_water(self):
        result = solve_cm(0.1, 20)  # below pure water viscosity
        assert result.status == "low"

    def test_status_high_above_glycerol(self):
        result = solve_cm(1e9, 20)
        assert result.status == "high"


class TestDensity:
    def test_pure_water(self):
        assert abs(density(0.0) - 0.99823) < 1e-5

    def test_pure_glycerol(self):
        assert abs(density(1.0) - 1.26108) < 1e-5

    def test_midpoint_interpolation(self):
        d = density(0.5)
        assert 1.1 < d < 1.15

    def test_default_temperature_is_20c(self):
        # default T reproduces the 20 °C table exactly
        assert abs(density(0.5) - density(0.5, 20)) < 1e-12

    def test_anchor_temperatures_match_tables(self):
        # each anchor reproduces its reference table at the pure-component ends
        assert abs(density(0.0, 15) - 0.99913) < 1e-5
        assert abs(density(1.0, 15) - 1.26415) < 1e-5
        assert abs(density(0.0, 20) - 0.99823) < 1e-5
        assert abs(density(0.0, 25) - 0.99708) < 1e-5
        assert abs(density(1.0, 20) - 1.26108) < 1e-5
        assert abs(density(1.0, 25) - 1.25802) < 1e-5
        assert abs(density(0.0, 30) - 0.99568) < 1e-5
        assert abs(density(1.0, 30) - 1.25495) < 1e-5

    def test_density_decreases_with_temperature(self):
        for w in [0.0, 0.5, 1.0]:
            assert density(w, 25) < density(w, 20)

    def test_temperature_interpolation_midpoint(self):
        # 22.5 °C sits halfway between the 20 and 25 anchors
        w = 0.5
        expected = (density(w, 20) + density(w, 25)) / 2
        assert abs(density(w, 22.5) - expected) < 1e-9

    def test_interpolation_within_new_anchor_range(self):
        # 17.5 °C brackets the 15.5/20 anchors — must lie between them
        w = 0.6
        assert density(w, 20) < density(w, 17.5) < density(w, 15.5)

    def test_extrapolation_beyond_anchor_range(self):
        # below 15 and above 30 the value extrapolates monotonically, not clamps
        w = 0.5
        assert density(w, 10) > density(w, 15)
        assert density(w, 40) < density(w, 30)

    def test_grid_density_strictly_falls_with_temperature(self):
        # invariant across the whole reference grid: hotter → less dense
        from glycerin_calculator.density_data import _DENS_ANCHORS
        n = len(_DENS_ANCHORS[0][1])
        for j in range(n):
            series = [tbl[j][1] for _, tbl in _DENS_ANCHORS]
            assert all(series[k] > series[k + 1] for k in range(len(series) - 1))

    def test_grid_columns_monotonic_in_concentration(self):
        from glycerin_calculator.density_data import _DENS_ANCHORS
        for _, tbl in _DENS_ANCHORS:
            assert all(tbl[i + 1][1] > tbl[i][1] for i in range(len(tbl) - 1))


class TestConversions:
    def test_vv_ww_roundtrip(self):
        for vv in [0.1, 0.3, 0.5, 0.7, 0.9]:
            assert abs(ww_to_vv(vv_to_ww(vv)) - vv) < 1e-9

    def test_vv_higher_than_ww_for_glycerol(self):
        # glycerol is denser than water, so v/v fraction < w/w fraction
        ww = 0.5
        assert ww_to_vv(ww) < ww

    def test_roundtrip_holds_at_any_temperature(self):
        for T in [15, 25, 37]:
            for vv in [0.1, 0.5, 0.9]:
                assert abs(ww_to_vv(vv_to_ww(vv, T), T) - vv) < 1e-9

    def test_conversion_tracks_temperature(self):
        # pure-component densities shift with T, so the v/v↔w/w mapping moves too
        assert vv_to_ww(0.86, 25) != vv_to_ww(0.86, 20)


class TestCalculate:
    def test_basic_case(self):
        r = calculate(60, 20, 100, 0, 86)
        assert r.error is None
        assert r.ms > 0
        assert r.final_mass > 100

    def test_target_too_high(self):
        r = calculate(5000, 20, 100, 0, 86)
        assert r.error is not None
        assert "unreachable" in r.error.lower()

    def test_stock_too_dilute(self):
        # target requires 80% but stock is only 50%
        mu_80 = mix_visc(0.80, 20)
        r = calculate(mu_80, 20, 100, 0, 50)
        assert r.error is not None
        assert "stock" in r.error.lower()

    def test_target_below_current(self):
        mu_50 = mix_visc(0.50, 20)
        r = calculate(mu_50 * 0.5, 20, 100, 50, 86)
        assert r.error is not None

    def test_stock_basis_changes_the_stock(self):
        r_ww = calculate(60, 20, 100, 0, 86, stock_basis="ww")
        r_vv = calculate(60, 20, 100, 0, 86, stock_basis="vv")
        # 86% v/v is a stronger liquid than 86% w/w → less of it needed
        assert r_vv.ms < r_ww.ms

    def test_measure_mass_takes_amount_as_grams(self):
        r = calculate(60, 20, 250, 0, 86, measure="mass")
        assert r.m0 == 250
        assert abs(r.V0 - 250 / density(0.0, 20)) < 1e-9

    def test_measure_volume_takes_amount_as_millilitres(self):
        r = calculate(60, 20, 250, 0, 86, measure="volume")
        assert r.V0 == 250
        assert abs(r.m0 - 250 * density(r.w0, 20)) < 1e-9

    def test_w0_basis_is_read_independently(self):
        # glycerol is denser than water, so 50% v/v is a larger mass fraction
        r_ww = calculate(60, 20, 100, 50, 99, w0_basis="ww")
        r_vv = calculate(60, 20, 100, 50, 99, w0_basis="vv")
        assert r_vv.w0 > r_ww.w0
        assert abs(r_ww.w0 - 0.50) < 1e-12
        assert abs(r_vv.w0 - vv_to_ww(0.50, 20)) < 1e-12

    def test_the_two_bases_do_not_interfere(self):
        # w0_basis must not touch the stock, and stock_basis must not touch the
        # base — the whole point of splitting them apart.
        ref = calculate(60, 20, 100, 50, 86, w0_basis="ww", stock_basis="ww")
        assert calculate(60, 20, 100, 50, 86, w0_basis="vv", stock_basis="ww").ws == ref.ws
        assert calculate(60, 20, 100, 50, 86, w0_basis="ww", stock_basis="vv").w0 == ref.w0

    def test_measure_does_not_touch_concentrations(self):
        # switching how you dispense must not move any mass fraction
        a = calculate(60, 20, 100, 20, 86, measure="mass")
        b = calculate(60, 20, 100, 20, 86, measure="volume")
        assert (a.w0, a.ws, a.wf) == (b.w0, b.ws, b.wf)

    def test_all_four_label_combinations_are_distinct(self):
        seen = {
            (wb, sb): calculate(60, 20, 100, 40, 86, w0_basis=wb, stock_basis=sb)
            for wb in ("ww", "vv") for sb in ("ww", "vv")
        }
        assert len({(r.w0, r.ws) for r in seen.values()}) == 4

    def test_mass_and_volume_agree_through_density(self):
        r = calculate(60, 20, 100, 0, 86)
        assert abs(r.Vs - r.ms / density(r.ws, 20)) < 1e-9
        assert abs(r.final_vol - r.final_mass / density(r.wf, 20)) < 1e-9

    def test_same_physical_stock_gives_the_same_answer(self):
        # "86%" names a different liquid on each label, which is why the two
        # settings report different amounts. Feed both the *same* stock and the
        # answers must coincide.
        eq_vv = ww_to_vv(0.86, 20) * 100
        r_ww = calculate(3, 20, 1000, 0, 86, stock_basis="ww")
        r_vv = calculate(3, 20, 1000, 0, eq_vv, stock_basis="vv")
        assert abs(r_ww.ms - r_vv.ms) < 1e-9
        assert abs(r_ww.Vs - r_vv.Vs) < 1e-9

    def test_every_setting_hits_the_target_viscosity(self):
        for w0_basis in ("ww", "vv"):
            for stock_basis in ("ww", "vv"):
                for measure in ("mass", "volume"):
                    r = calculate(3, 20, 1000, 10, 86, w0_basis, stock_basis, measure)
                    wf = (r.m0 * r.w0 + r.ms * r.ws) / (r.m0 + r.ms)
                    assert abs(wf - r.wf) < 1e-9
                    assert abs(mix_visc(wf, 20) - 3) < 1e-6

    def test_dilute_stock_error_quotes_the_stock_label(self):
        mu_80 = mix_visc(0.80, 20)
        assert "(w/w)" in calculate(mu_80, 20, 100, 0, 50, stock_basis="ww").error
        assert "(v/v)" in calculate(mu_80, 20, 100, 0, 50, stock_basis="vv").error


class TestCalculateBatch:
    def test_mode_flag(self):
        r = calculate_batch(60, 20, 500, 0, 86)
        assert r.mode == "batch"
        assert r.error is None

    def test_both_amounts_solved(self):
        r = calculate_batch(60, 20, 500, 0, 86)
        assert r.m0 > 0          # base solution mass
        assert r.ms > 0          # stock mass
        assert r.final_mass == 500

    def test_measuring_by_mass_balances_exactly(self):
        # weighing out, the components sum to the requested final mass exactly
        r = calculate_batch(60, 20, 500, 0, 86, measure="mass")
        assert abs((r.m0 + r.ms) - 500) < 1e-9

    def test_measuring_by_volume_pins_final_volume(self):
        r = calculate_batch(60, 20, 500, 0, 86, measure="volume")
        assert abs(r.final_vol - 500) < 1e-9
        # glycerol-water mixing contracts → components sum to more than final
        assert r.V0 + r.Vs > r.final_vol

    def test_mass_balance_hits_target(self):
        # the two solved amounts, recombined, should reproduce the target viscosity
        r = calculate_batch(60, 20, 500, 0, 86)
        wf_check = (r.m0 * r.w0 + r.ms * r.ws) / (r.m0 + r.ms)
        assert abs(mix_visc(wf_check, 20) - 60) < 0.5

    def test_scales_with_final_amount(self):
        small = calculate_batch(60, 20, 250, 0, 86)
        big = calculate_batch(60, 20, 500, 0, 86)
        assert big.ms > small.ms
        assert big.m0 > small.m0

    def test_target_too_high(self):
        r = calculate_batch(5000, 20, 500, 0, 86)
        assert r.error is not None

    def test_stock_too_dilute(self):
        mu_80 = mix_visc(0.80, 20)
        r = calculate_batch(mu_80, 20, 500, 0, 50)
        assert r.error is not None
        assert "stock" in r.error.lower()


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class TestHTTP:
    def test_index_ok(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Glycerin" in resp.text

    def test_measure_mass_reports_grams(self):
        resp = client.post("/calculate", data={
            "target_mu": 60, "temperature": 20, "amount": 100,
            "w0_pct": 0, "stock_pct": 86, "measure": "mass",
        })
        assert resp.status_code == 200
        assert "final mass" in resp.text
        assert ">g<" in resp.text

    def test_measure_volume_reports_millilitres(self):
        resp = client.post("/calculate", data={
            "target_mu": 60, "temperature": 20, "amount": 100,
            "w0_pct": 0, "stock_pct": 86, "measure": "volume",
        })
        assert resp.status_code == 200
        assert "final volume" in resp.text
        assert ">mL<" in resp.text

    def test_stock_label_is_echoed_with_its_equivalent(self):
        # a v/v-labelled stock weighed out in grams — the combination the old
        # single toggle could not express
        resp = client.post("/calculate", data={
            "target_mu": 60, "temperature": 20, "amount": 100,
            "w0_pct": 0, "stock_pct": 86,
            "stock_basis": "vv", "measure": "mass",
        })
        assert resp.status_code == 200
        assert "86% v/v ≡ 88.6% w/w" in resp.text
        assert ">g<" in resp.text

    def test_each_concentration_keeps_its_own_label(self):
        resp = client.post("/calculate", data={
            "mode": "batch", "target_mu": 60, "final_amount": 500,
            "temperature": 20, "amount": 100,
            "w0_pct": 20, "stock_pct": 86,
            "w0_basis": "vv", "stock_basis": "ww", "measure": "mass",
        })
        assert resp.status_code == 200
        assert "base (20% v/v)" in resp.text
        assert "86% (w/w) stock" in resp.text

    def test_calculate_error_case(self):
        resp = client.post("/calculate", data={
            "target_mu": 9999, "temperature": 20, "amount": 100,
            "w0_pct": 0, "stock_pct": 86,
        })
        assert resp.status_code == 200
        assert "result-error" in resp.text

    def test_calculate_batch_mode(self):
        resp = client.post("/calculate", data={
            "mode": "batch", "target_mu": 60, "final_amount": 500,
            "temperature": 20, "amount": 100,
            "w0_pct": 0, "stock_pct": 86,
        })
        assert resp.status_code == 200
        assert "TO MAKE 500 g" in resp.text
