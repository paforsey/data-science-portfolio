"""Regenerates data.json for the International Roaming Scenario Tool from the
case study's notebook exports.

Run from the international-roaming/ directory, after the notebook has been
re-executed (which refreshes data/synthetic/ and data/powerbi/):

    cd case-studies/international-roaming
    python3 web/build_data.py

Reads the Power BI export tables and writes web/data.json — the only file
index.html fetches at runtime, and the only file that ever needs to change
after a notebook re-run.

Data contract, in brief (see web/README.md for the full version):

  portfolio   full 13-point price grid, "as fitted" and "joint sensitivity"
              cases, unconditioned on macro scenario (macro_shift = 0). This
              is what the tool calls the "Base" economic condition.
  scenarios   Expansion / Contraction only, each at exactly the three prices
              the macro simulation was run at (1.00x / 1.15x / 1.20x), always
              under the "joint sensitivity" case — that's the only case the
              macro simulation covers, so there is no "as fitted" curve to
              show once a non-Base scenario is selected. The 1.15x point is
              a fixed stress-test price (the joint-sensitivity case's
              revenue-maximizing price, STRESS_TEST_PRICE below) — it is NOT
              tied to meta.recommended_price, which is read from the
              as-fitted case and currently sits at the 1.20x cap. The two
              happen to coincide when the recommendation is 1.15x, but must
              not be assumed equal: fact_macro_scenario only has rows at
              1.00/1.15/1.20, so if recommended_price is ever something else
              (as it is now, at 1.20x), scenario_prices would otherwise
              collide or miss a grid point. fact_macro_scenario also
              contains a "Base" row at those same three prices, from a
              separate (300-iteration) run of the same unconditioned case;
              it is deliberately NOT surfaced in the UI as a second "Base"
              source — see README — but is checked below for consistency
              with `portfolio` so a large divergence fails the build.
  segments    every segment (Dormant included), full 13-point grid, revenue
              and purchasers from the as-fitted replay (Base economy, both
              sensitivity scales 1.0), the same run as the headline figures.
              Segment medians don't add up to a portfolio median, so each
              segment gets the portfolio median in proportion to its share of
              the simulation mean at that price: rows sum exactly to the
              headline figures, and their changes to the headline change.
              The replay is asserted to reproduce the published as-fitted
              revenue and purchaser medians at every price.
  purchasers  Now simulated (not just segment-level): portfolio (both
              cases, full grid) and Expansion/Contraction (3 prices) carry
              purchasers_p5/_median/_p95 from the same simulate() draws as
              revenue — added to the notebook's inner loop as a per-
              iteration count of distinct accounts with >=1 non-null trip
              (np.bincount over account_id), paired with revenue rather
              than a second independent simulation. eligible_accounts is
              the forward-panel population those counts are drawn from
              (N_ACCOUNTS_PANEL), constant across every row.
              Expansion/Contraction additionally carry a genuinely paired
              revenue/purchaser difference (1.15x vs 1.00x, same iterations)
              under `paired_at_stress_price` — preferred over subtracting
              marginal medians per the tool's spec (§12), and used by the
              page whenever the scenario and selected price make it valid.
              Named for the fixed 1.15x stress-test price, not for whichever
              price is currently recommended (see `scenarios` above).
              Segment-level purchasers remain the Track-A deterministic
              figure above; no plan to simulate intervals at that grain
              (see the scoping note in README's git history).
  probCurve   Population-mean P(null)/P(partial)/P(full) by price and case —
              the State Model's price-response mechanism itself, not a
              simulated quantity. Not conditioned on macro scenario: the
              macro shift only ever affects trip occurrence, never these
              state probabilities, so this curve is the same regardless of
              which economic scenario is selected in the UI.
  sensitivityGrid
              Independent response_scale x depth_scale controls, replacing
              the old bundled "Behavior Case" toggle. 3 points each
              (1.0, midpoint, the diagnostic-derived ceiling), full price
              grid, Base economy only — Expansion/Contraction stay fixed at
              the ceiling point (RESPONSE_SCALE_GRID[-1] /
              DEPTH_SCALE_GRID[-1] in the notebook), unchanged from before
              this grid existed. `cells["<ri>_<di>"]` indexes into
              `responseScale[ri]` x `depthScale[di]`. Purely additive at the
              notebook/export layer — the original two-case sweep
              (`portfolio`, `dim_model_case`, `fact_portfolio_simulation`)
              is untouched, so nothing depending on it needed to change.
  travelers   National forecast of U.S. citizen international air departures
              for each calendar month, ordered January to December (M1-M12
              on the page), covering the 12 months after the latest I-92
              actual. Built
              from published actuals, not the simulation: each month is the
              same month a year earlier times year-to-date growth. Expansion /
              Contraction scale it by the simulation's own effect on travel
              volume (travelers summed over occurring trips, median vs. Base,
              from the replayed 1.00x runs); p5/p95 apply the simulation's
              spread in that volume. Not scaled by meta.scale_factor: these are
              already national figures.
  purchasersByMonth
              Distinct accounts buying a pass in each forecast month, split
              by segment (Dormant included, so segments cover the whole
              panel), from the same replay. One cell per control position the
              purchaser chart already reflects: base[responseIdx][priceIdx]
              over the full grid, expansion/contraction[priceIdx] over the
              three scenario prices. Depth scale never changes purchasers, so
              it has no axis here. Segments carry per-iteration means, which
              add up to the total mean; the total also carries p5/p95. Every
              cell's replay is asserted to reproduce its published annual
              purchaser median.
  meta.scale_factor
              National addressable trips (I-92 x MARKET_SHARE) / forecast
              panel trips: the factor market_sizing.parquet effectively
              applies to as-fitted revenue. All figures in this file stay at
              model scale (revenue and counts unrounded to integers so scaling
              stays exact); the page multiplies every count and dollar figure
              by this one factor on load. The build asserts it reproduces
              market_sizing's scaled revenue at every price.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent  # international-roaming/
PBI = BASE / "data" / "powerbi"
SYN = BASE / "data" / "synthetic"
OUT = Path(__file__).resolve().parent / "data.json"  # web/data.json

# Must match the notebook's Section 5.1 assumption exactly (same constant,
# duplicated here only for display metadata — the actual scaled figures are
# read from market_sizing.parquet, not recomputed).
MARKET_SHARE = 0.30

MACRO_CONSISTENCY_TOLERANCE = 0.05  # 5% — "Base" cross-check, see module docstring

FORWARD_MONTHS = 12
NULL_STATE = 0  # column order p_null, p_partial, p_full


def build_forward_panel():
    """Rebuilds the notebook's forward panel ("Build Forward Panel" cell) as
    row-aligned arrays in the same trip order simulate() draws against."""
    trips = pd.read_parquet(SYN / "trips.parquet")
    macro = pd.read_parquet(SYN / "macro.parquet")
    prob_scen = pd.read_parquet(SYN / "sim_prob_scenarios.parquet")
    rev_scen = pd.read_parquet(SYN / "sim_revenue_scenarios.parquet")

    last12 = trips.loc[trips["month"] >= trips["month"].max() - 11].copy()
    last12["fwd_month"] = last12["month"] - last12["month"].min()
    last12["hist_macro_mult"] = last12["month"].map(macro.set_index("month")["travel_multiplier"]).to_numpy()

    months = np.arange(FORWARD_MONTHS)
    fwd_season = 1.0 + 0.15 * np.sin(2 * np.pi * (months - 2) / 12) + 0.06 * (months == 11)

    valid_trip_ids = set(prob_scen["trip_id"].unique()) & set(rev_scen["trip_id"].unique())
    panel = last12.loc[last12["trip_id"].isin(valid_trip_ids)]
    fwd_month = panel["fwd_month"].to_numpy()

    account_idx, account_ids = pd.factorize(panel["account_id"].to_numpy())
    account_segment = (
        pd.read_parquet(PBI / "bridge_account_segment.parquet")
        .set_index("account_id")["segment_id"]
        .reindex(account_ids)
    )
    assert account_segment.notna().all(), "forward-panel account missing from bridge_account_segment"

    return {
        "trip_ids": panel["trip_id"].to_numpy(),
        "month": fwd_month,
        "season": fwd_season[fwd_month],
        "hist_mult": panel["hist_macro_mult"].to_numpy(),
        "lines_traveling": panel["lines_traveling"].to_numpy(dtype=float),
        "account_idx": account_idx,
        "account_segment_id": account_segment.astype(int).to_numpy(),
        "z_last": float(macro.sort_values("month")["macro_index"].tail(3).mean()),
        "prob_scen": prob_scen,
        "rev_scen": rev_scen,
    }


def replay_forward_year(panel, n_iter, macro_shift, seed, state_prob, segment_onehot, state_revenue=None):
    """Replays the notebook's simulate() random stream (antithetic=True, its
    default) draw for draw. Returns per-iteration distinct-account counts:
    monthly_travelers [n_iter x 12], annual_travelers [n_iter],
    annual_person_trips [n_iter] (travelers summed over occurring trips),
    annual_purchasers [n_iter], monthly_purchasers_by_segment
    [n_iter x segments x 12], and annual_purchasers_by_segment
    [n_iter x segments]. Trip occurrence, and so the traveler counts, doesn't
    depend on `state_prob`; only purchases do. Given `state_revenue`
    [trips x 3], also returns annual_revenue [n_iter], summed exactly as
    simulate() sums it, and annual_revenue_by_segment [n_iter x segments]."""
    n = len(panel["trip_ids"])
    month = panel["month"]
    account_idx = panel["account_idx"]
    n_accounts = int(account_idx.max()) + 1
    account_month_key = account_idx * FORWARD_MONTHS + month
    cumulative_probability = state_prob.cumsum(axis=1)
    segment_matrix = segment_onehot.T  # [segments x accounts]
    trip_segment = segment_onehot.argmax(axis=1)[account_idx]

    def any_per_account_month(trip_flags):
        return (
            np.bincount(account_month_key, weights=trip_flags, minlength=n_accounts * FORWARD_MONTHS)
            .reshape(n_accounts, FORWARD_MONTHS) > 0
        )

    rng = np.random.default_rng(seed)
    independent_paths = (n_iter + 1) // 2
    cached_paths = []

    n_segments = segment_onehot.shape[1]
    out = {
        "monthly_travelers": np.zeros((n_iter, FORWARD_MONTHS)),
        "annual_travelers": np.zeros(n_iter),
        "annual_purchasers": np.zeros(n_iter),
        "monthly_purchasers_by_segment": np.zeros((n_iter, n_segments, FORWARD_MONTHS)),
        "annual_purchasers_by_segment": np.zeros((n_iter, n_segments)),
        "annual_person_trips": np.zeros(n_iter),
    }
    if state_revenue is not None:
        out["annual_revenue"] = np.zeros(n_iter)
        out["annual_revenue_by_segment"] = np.zeros((n_iter, n_segments))

    for iteration in range(n_iter):
        if iteration < independent_paths:
            macro_shocks = rng.normal(0, 0.35, 12)
            travel_share_shift = rng.normal(0, 0.03)
            cached_paths.append((macro_shocks, travel_share_shift))
        else:
            macro_shocks, travel_share_shift = cached_paths[iteration - independent_paths]
            macro_shocks, travel_share_shift = -macro_shocks, -travel_share_shift

        macro_index = np.zeros(12)
        macro_index[0] = 0.85 * panel["z_last"] + macro_shocks[0]
        for month_index in range(1, 12):
            macro_index[month_index] = 0.85 * macro_index[month_index - 1] + macro_shocks[month_index]
        macro_index += macro_shift

        travel_multiplier = np.exp(0.55 * macro_index) * (1.0 + travel_share_shift)
        occurrence_probability = np.clip(travel_multiplier[month] * panel["season"] / panel["hist_mult"], 0, 1)
        occurs = rng.random(n) < occurrence_probability
        state = (rng.random(n)[:, None] > cumulative_probability).sum(axis=1)

        traveled = any_per_account_month(occurs)
        purchased = any_per_account_month(occurs & (state != NULL_STATE))
        purchased_in_year = purchased.any(axis=1)

        out["monthly_travelers"][iteration] = traveled.sum(axis=0)
        out["annual_travelers"][iteration] = traveled.any(axis=1).sum()
        out["annual_person_trips"][iteration] = panel["lines_traveling"][occurs].sum()
        out["annual_purchasers"][iteration] = purchased_in_year.sum()
        out["monthly_purchasers_by_segment"][iteration] = segment_matrix @ purchased.astype(float)
        out["annual_purchasers_by_segment"][iteration] = segment_matrix @ purchased_in_year.astype(float)

        if state_revenue is not None:
            trip_revenue = np.where(occurs, state_revenue[np.arange(n), state], 0.0)
            out["annual_revenue"][iteration] = trip_revenue.sum()
            out["annual_revenue_by_segment"][iteration] = np.bincount(
                trip_segment, weights=trip_revenue, minlength=n_segments
            )

    return out


def main():
    dim_price = pd.read_parquet(PBI / "dim_price.parquet")
    dim_segment = pd.read_parquet(PBI / "dim_segment.parquet")
    dim_model_case = pd.read_parquet(PBI / "dim_model_case.parquet")
    dim_assumption = pd.read_parquet(PBI / "dim_assumption.parquet")
    fact_portfolio = pd.read_parquet(PBI / "fact_portfolio_simulation.parquet")
    fact_macro = pd.read_parquet(PBI / "fact_macro_scenario.parquet")
    fact_seg_rev = pd.read_parquet(PBI / "fact_segment_revenue.parquet")
    fact_prob_curve = pd.read_parquet(PBI / "fact_probability_curve.parquet")
    fact_sensitivity = pd.read_parquet(PBI / "fact_sensitivity_grid.parquet")

    run_ids = set(
        pd.concat([
            dim_price["run_id"], dim_segment["run_id"], dim_model_case["run_id"],
            fact_portfolio["run_id"], fact_macro["run_id"], fact_seg_rev["run_id"],
            fact_prob_curve["run_id"], fact_sensitivity["run_id"],
        ]).unique()
    )
    assert len(run_ids) == 1, f"export tables span multiple run_ids: {run_ids}"
    run_id = run_ids.pop()

    grid = sorted(dim_price["price_multiplier"].round(4).unique().tolist())
    recommended_price = float(
        dim_price.loc[dim_price["is_recommended"], "price_multiplier"].iloc[0]
    )
    current_price = 1.0
    assert any(abs(g - current_price) < 1e-9 for g in grid), "1.00x missing from price grid"
    assert any(abs(g - recommended_price) < 1e-9 for g in grid), "recommended price missing from grid"

    # eligible_accounts is a single constant (the forward-panel population);
    # confirm it really is constant before treating it as a scalar downstream.
    assert fact_portfolio["eligible_accounts"].nunique() == 1, (
        "eligible_accounts is not constant in fact_portfolio_simulation"
    )
    assert fact_macro["eligible_accounts"].nunique() == 1, (
        "eligible_accounts is not constant in fact_macro_scenario"
    )
    eligible_accounts = int(fact_portfolio["eligible_accounts"].iloc[0])
    assert eligible_accounts == int(fact_macro["eligible_accounts"].iloc[0]), (
        "eligible_accounts differs between fact_portfolio_simulation and fact_macro_scenario"
    )

    # ---- portfolio: full grid, both cases, unconditioned (= "Base") ----
    portfolio = {}
    for case in ["as fitted", "joint sensitivity"]:
        d = fact_portfolio[fact_portfolio["case"] == case].sort_values("price_multiplier")
        assert d["price_multiplier"].round(4).tolist() == grid, f"{case}: price grid mismatch"
        assert (d["p5"] <= d["median"]).all() and (d["median"] <= d["p95"]).all(), f"{case}: p5<=median<=p95 violated"
        assert (d["p5"] >= 0).all(), f"{case}: negative revenue bound"
        assert (d["purchasers_p5"] <= d["purchasers_median"]).all() and (
            d["purchasers_median"] <= d["purchasers_p95"]
        ).all(), f"{case}: purchasers p5<=median<=p95 violated"
        assert (d["purchasers_p5"] >= 0).all(), f"{case}: negative purchasers bound"
        assert (d["purchasers_p95"] <= eligible_accounts + 1e-6).all(), (
            f"{case}: purchasers p95 exceeds eligible_accounts"
        )
        portfolio[case] = {
            "revenue_p5": d["p5"].round(2).tolist(),
            "revenue_median": d["median"].round(2).tolist(),
            "revenue_p95": d["p95"].round(2).tolist(),
            "purchasers_p5": d["purchasers_p5"].round(2).tolist(),
            "purchasers_median": d["purchasers_median"].round(2).tolist(),
            "purchasers_p95": d["purchasers_p95"].round(2).tolist(),
        }

    # ---- scenarios: Expansion / Contraction, 3 prices, joint sensitivity only ----
    # STRESS_TEST_PRICE is the joint-sensitivity case's revenue-maximizing price —
    # the fixed price the notebook's macro-scenario cell was run at (1.00/1.15/1.20
    # literally, independent of Model 04's RECOMMENDED_PRICE). Deliberately NOT
    # `recommended_price`: that's read from the as-fitted case and can land
    # anywhere on the grid (currently 1.20x, the cap) without a matching row in
    # fact_macro_scenario. See the `scenarios` entry in the module docstring.
    STRESS_TEST_PRICE = 1.15
    assert any(abs(g - STRESS_TEST_PRICE) < 1e-9 for g in grid), (
        "stress-test price missing from price grid"
    )
    scenario_prices = [1.0, STRESS_TEST_PRICE, 1.2]
    scenarios = {}
    for key, parquet_scenario in [("expansion", "Expansion"), ("contraction", "Contraction")]:
        d = fact_macro[fact_macro["scenario"] == parquet_scenario].sort_values("price")
        prices = d["price"].round(4).tolist()
        assert prices == [round(p, 4) for p in scenario_prices], (
            f"{key}: expected prices {scenario_prices}, got {prices}"
        )
        assert (d["p5"] <= d["median"]).all() and (d["median"] <= d["p95"]).all(), f"{key}: p5<=median<=p95 violated"
        assert (d["purchasers_p5"] <= d["purchasers_median"]).all() and (
            d["purchasers_median"] <= d["purchasers_p95"]
        ).all(), f"{key}: purchasers p5<=median<=p95 violated"
        assert (d["purchasers_p5"] >= 0).all(), f"{key}: negative purchasers bound"
        assert (d["purchasers_p95"] <= eligible_accounts + 1e-6).all(), (
            f"{key}: purchasers p95 exceeds eligible_accounts"
        )

        # Genuinely paired revenue/purchaser difference at the fixed stress-test
        # price (1.15x vs 1.00x, same simulation draws) — only defined there,
        # since that's the only pair the notebook's paired-difference cell
        # computes. Not the recommended price (see STRESS_TEST_PRICE above).
        stress_row = d.loc[d["price"].round(4) == round(STRESS_TEST_PRICE, 4)].iloc[0]
        assert pd.notna(stress_row["purchasers_paired_median"]), (
            f"{key}: missing paired purchaser difference at the stress-test price"
        )
        paired_at_stress_price = {
            "price": STRESS_TEST_PRICE,
            "revenue_paired_p5": round(float(stress_row["paired_p5"]), 2),
            "revenue_paired_median": round(float(stress_row["paired_median"]), 2),
            "revenue_paired_p95": round(float(stress_row["paired_p95"]), 2),
            "purchasers_paired_p5": round(float(stress_row["purchasers_paired_p5"]), 1),
            "purchasers_paired_median": round(float(stress_row["purchasers_paired_median"]), 1),
            "purchasers_paired_p95": round(float(stress_row["purchasers_paired_p95"]), 1),
        }

        scenarios[key] = {
            "price": prices,
            "revenue_p5": d["p5"].round(2).tolist(),
            "revenue_median": d["median"].round(2).tolist(),
            "revenue_p95": d["p95"].round(2).tolist(),
            "purchasers_p5": d["purchasers_p5"].round(2).tolist(),
            "purchasers_median": d["purchasers_median"].round(2).tolist(),
            "purchasers_p95": d["purchasers_p95"].round(2).tolist(),
            "paired_at_stress_price": paired_at_stress_price,
        }

    # Base-row consistency check: fact_macro_scenario's own "Base" row (separate,
    # 300-iteration run) should roughly agree with `portfolio["joint sensitivity"]`
    # at the same three prices. This isn't surfaced in the UI (see docstring) but a
    # large drift here means the two simulations have come apart and needs a look.
    macro_base = fact_macro[fact_macro["scenario"] == "Base"].sort_values("price")
    ref_df = fact_portfolio[fact_portfolio["case"] == "joint sensitivity"].copy()
    ref = ref_df.set_index(ref_df["price_multiplier"].round(4))["median"]
    for _, row in macro_base.iterrows():
        p = round(float(row["price"]), 4)
        if p in ref.index:
            drift = abs(row["median"] - ref[p]) / ref[p]
            assert drift < MACRO_CONSISTENCY_TOLERANCE, (
                f"Base macro-scenario row at {p}x drifted {drift:.1%} from the "
                f"unconditioned joint-sensitivity median — check the notebook rerun"
            )

    # ---- segment metadata: every segment, Dormant included ----
    # The contribution curves (seg_curve) come from the as-fitted replay further
    # down; Dormant is a row there so the rows add up to the headline totals.
    segments_sorted = dim_segment.sort_values("sort_order")
    seg_order = segments_sorted["segment_id"].astype(str).tolist()

    seg_meta = {}
    for _, r in segments_sorted.iterrows():
        sid = str(r["segment_id"])
        seg_meta[sid] = {
            "name": r["segment"],
            "headline": r["headline"],
            "description": r["description"] if pd.notna(r["description"]) else "",
            "accounts": int(r["accounts"]),
            "acct_share": round(float(r["acct_share"]), 4),
            "rev_share": round(float(r["rev_share"]), 4),
            "business": round(float(r["business"]), 4),
            "rev_per_acct": round(float(r["rev_per_acct"]), 2),
        }

    # ---- dormant segment: disclosed, excluded from pricing comparisons ----
    dormant_rows = dim_segment[dim_segment["is_dormant"]]
    dormant = None
    if len(dormant_rows):
        r = dormant_rows.iloc[0]
        dormant = {
            "name": r["segment"],
            "accounts": int(r["accounts"]),
            "acct_share": round(float(r["acct_share"]), 4),
            "rev_share": round(float(r["rev_share"]), 4),
            "rev_per_acct": round(float(r["rev_per_acct"]), 2),
        }

    # ---- coverage-state probability curve: full grid, response-scale only ----
    # Not conditioned on economic scenario (macro shift never touches these) or
    # depth_scale (which only touches revenue magnitude, never coverage-state
    # probability). Indexed 0/1/2 to match sensitivityGrid.responseScale below.
    prob_curve_response_grid = sorted(fact_prob_curve["response_scale"].unique().tolist())
    assert len(prob_curve_response_grid) == 3, "expected a 3-point response_scale grid in prob curve"
    prob_curve = {}
    for ri, rs in enumerate(prob_curve_response_grid):
        d = fact_prob_curve[np.isclose(fact_prob_curve["response_scale"], rs)].sort_values("price_multiplier")
        assert d["price_multiplier"].round(4).tolist() == grid, f"prob curve [{ri}]: price grid mismatch"
        totals = d["p_null"] + d["p_partial"] + d["p_full"]
        assert np.allclose(totals, 1.0, atol=1e-6), f"prob curve [{ri}]: probabilities don't sum to 1"
        assert ((d[["p_null", "p_partial", "p_full"]] >= 0).all()).all(), f"prob curve [{ri}]: negative probability"
        prob_curve[str(ri)] = {
            "p_null": d["p_null"].round(4).tolist(),
            "p_partial": d["p_partial"].round(4).tolist(),
            "p_full": d["p_full"].round(4).tolist(),
        }

    # ---- sensitivity grid: independent response-scale x depth-scale controls ----
    # Base economy only (Expansion/Contraction stay fixed at the ceiling point,
    # unchanged — see build note in the notebook's "Sweep Sensitivity Grid" cell).
    response_scale_grid = sorted(fact_sensitivity["response_scale"].unique().tolist())
    depth_scale_grid = sorted(fact_sensitivity["depth_scale"].unique().tolist())
    assert len(response_scale_grid) == 3, "expected a 3-point response_scale grid"
    assert len(depth_scale_grid) == 3, "expected a 3-point depth_scale grid"
    assert abs(response_scale_grid[0] - 1.0) < 1e-6, "response_scale grid should start at 1.0"
    assert abs(depth_scale_grid[0] - 1.0) < 1e-6, "depth_scale grid should start at 1.0"

    sensitivity_cells = {}
    for ri, rs in enumerate(response_scale_grid):
        for di, ds in enumerate(depth_scale_grid):
            d = fact_sensitivity[
                np.isclose(fact_sensitivity["response_scale"], rs)
                & np.isclose(fact_sensitivity["depth_scale"], ds)
            ].sort_values("price_multiplier")
            assert d["price_multiplier"].round(4).tolist() == grid, (
                f"sensitivity grid [{ri},{di}]: price grid mismatch"
            )
            assert (d["p5"] <= d["median"]).all() and (d["median"] <= d["p95"]).all(), (
                f"sensitivity grid [{ri},{di}]: revenue p5<=median<=p95 violated"
            )
            assert (d["purchasers_p5"] <= d["purchasers_median"]).all() and (
                d["purchasers_median"] <= d["purchasers_p95"]
            ).all(), f"sensitivity grid [{ri},{di}]: purchasers p5<=median<=p95 violated"
            assert (d["p5"] >= 0).all() and (d["purchasers_p5"] >= 0).all(), (
                f"sensitivity grid [{ri},{di}]: negative value"
            )
            sensitivity_cells[f"{ri}_{di}"] = {
                "revenue_p5": d["p5"].round(2).tolist(),
                "revenue_median": d["median"].round(2).tolist(),
                "revenue_p95": d["p95"].round(2).tolist(),
                "purchasers_p5": d["purchasers_p5"].round(2).tolist(),
                "purchasers_median": d["purchasers_median"].round(2).tolist(),
                "purchasers_p95": d["purchasers_p95"].round(2).tolist(),
            }

    sensitivity_grid_payload = {
        "responseScale": [round(v, 4) for v in response_scale_grid],
        "depthScale": [round(v, 4) for v in depth_scale_grid],
        "cells": sensitivity_cells,
    }

    assert [round(v, 4) for v in prob_curve_response_grid] == [round(v, 4) for v in response_scale_grid], (
        "probability-curve response_scale grid disagrees with the sensitivity grid's"
    )

    assumption_values = dim_assumption.set_index("assumption")["value"]

    # ---- market sizing: I-92 real-world travel anchor x assumed carrier share ----
    # Reads the notebook's Section 5.1 output (market_sizing.parquet) rather than
    # recomputing it, so the tool and the notebook/deck always agree by construction.
    market_sizing_df = pd.read_parquet(SYN / "market_sizing.parquet")
    market_sizing_payload = {
        str(round(float(row["Price Multiplier"]), 4)): {
            "revenue_per_trip": round(float(row["Revenue per Trip (As Fitted)"]), 2),
            "scaled_annual_revenue": round(float(row["Scaled Annual Revenue"]), 2),
            "scaled_lift": round(float(row["Scaled Lift vs. Standard"]), 2),
            "share_of_target": round(float(row["Share of $100M Target"]), 4),
        }
        for _, row in market_sizing_df.iterrows()
    }
    i92 = pd.read_csv(BASE / "data" / "reference" / "us_i92_air_travel.csv")
    i92_annual = (
        i92.loc[~i92["Year"].isin([2020, 2021, 2026])]
        .groupby("Year")["U.S. Citizen Originating"]
        .sum()
    )
    i92_year = int(i92_annual.index.max())
    i92_trips = float(i92_annual.loc[i92_year])

    # ---- travelers: forward-year international travel volume by month ----
    # Replayed from the run's own random stream (see replay_forward_travel), then
    # checked against each run's published purchaser median at 1.00x: an exact
    # match means the occurrence draws, and so these counts, are the run's own.
    crn_seed = int(float(assumption_values["common random-number seed"]))
    sweep_iter = int(float(assumption_values["sweep iterations per price"]))
    macro_iter = int(float(assumption_values["macro iterations per scenario"]))

    panel = build_forward_panel()
    assert int(panel["account_idx"].max()) + 1 == eligible_accounts, (
        "rebuilt forward panel's account count differs from eligible_accounts"
    )
    prob_idx = (
        panel["prob_scen"]
        .assign(price_multiplier=lambda d: d["price_multiplier"].round(4))
        .set_index(["response_scenario", "price_multiplier", "trip_id"])
        .sort_index()
    )

    def state_prob(response_scenario, price):
        return (
            prob_idx.loc[(response_scenario, round(price, 4)), ["p_null", "p_partial", "p_full"]]
            .reindex(panel["trip_ids"])
            .to_numpy()
        )

    macro_shifts = fact_macro.groupby("scenario")["macro_shift"].first()
    assert abs(macro_shifts["Base"]) < 1e-9, "Base macro shift should be 0"

    # Stacking order for the monthly purchaser chart: every panel segment,
    # Dormant included, so segment counts add up to the portfolio total.
    stack_segments = dim_segment.sort_values("sort_order")
    stack_segment_ids = stack_segments["segment_id"].astype(str).tolist()
    segment_onehot = (
        panel["account_segment_id"][:, None] == stack_segments["segment_id"].to_numpy()[None, :]
    ).astype(float)
    assert (segment_onehot.sum(axis=1) == 1).all(), "every panel account needs exactly one segment"

    # response_scale_grid index -> the response_scenario its probabilities are stored under
    response_scenario_names = ["base", "mid", "stronger"]

    rev_idx = (
        panel["rev_scen"]
        .assign(price_multiplier=lambda d: d["price_multiplier"].round(4))
        .set_index(["depth_scenario", "price_multiplier", "trip_id"])
        .sort_index()
    )

    def state_revenue_as_fitted(price):
        return (
            rev_idx.loc[("reported", round(price, 4)), ["rev_null", "rev_partial", "rev_full"]]
            .reindex(panel["trip_ids"])
            .to_numpy()
        )

    fitted_median = (
        fact_portfolio[fact_portfolio["case"] == "as fitted"]
        .assign(p=lambda d: d["price_multiplier"].round(4))
        .set_index("p")["median"]
    )

    # Segment split of the as-fitted headline figures. Segment medians don't add
    # up to the portfolio median, so each segment gets the portfolio median in
    # proportion to its share of the simulation mean at that price; rows then
    # sum exactly to the headline figures, and their changes to its change.
    def allocate_to_segments(result):
        allocated = {}
        for metric, total_key, by_segment_key in [
            ("revenue", "annual_revenue", "annual_revenue_by_segment"),
            ("purchasers", "annual_purchasers", "annual_purchasers_by_segment"),
        ]:
            segment_mean = result[by_segment_key].mean(axis=0)
            allocated[metric] = np.median(result[total_key]) * segment_mean / segment_mean.sum()
        return allocated

    def replay_checked(label, n_iter, macro_shift, response_scenario, price, published, state_revenue=None):
        result = replay_forward_year(
            panel, n_iter, macro_shift, crn_seed, state_prob(response_scenario, price), segment_onehot,
            state_revenue=state_revenue,
        )
        replayed = np.median(result["annual_purchasers"])
        assert abs(replayed - published) < 1e-6, (
            f"{label}: replayed draws give a purchaser median of {replayed}, published is "
            f"{published}; simulate() or the forward panel changed, so update "
            f"replay_forward_year() to match the notebook"
        )
        total = result["monthly_purchasers_by_segment"].sum(axis=1)
        assert (total <= result["monthly_travelers"]).all(), f"{label}: monthly purchasers exceed travelers"
        return result

    def summarize_monthly_purchasers(result):
        by_segment = result["monthly_purchasers_by_segment"]  # [n_iter x segments x months]
        total = by_segment.sum(axis=1)
        return {
            "total_mean": total.mean(axis=0).round(1).tolist(),
            "total_p5": np.percentile(total, 5, axis=0).round(2).tolist(),
            "total_p95": np.percentile(total, 95, axis=0).round(2).tolist(),
            "segment_mean": {
                sid: by_segment[:, s, :].mean(axis=0).round(1).tolist()
                for s, sid in enumerate(stack_segment_ids)
            },
            "annual_segment_mean": {
                sid: round(float(result["annual_purchasers_by_segment"][:, s].mean()), 1)
                for s, sid in enumerate(stack_segment_ids)
            },
        }

    purchasers_by_month = {
        "segmentOrder": stack_segment_ids,
        "segmentLabels": dict(zip(stack_segment_ids, stack_segments["headline"])),
        "base": {},
    }
    current_price_runs = {}  # scenario key -> replay at 1.00x, for the traveler counts
    segment_rows = []  # as-fitted segment allocation, one per grid price

    for ri, response_scale in enumerate(response_scale_grid):
        cells = []
        for price in grid:
            published = fact_sensitivity.loc[
                np.isclose(fact_sensitivity["response_scale"], response_scale)
                & np.isclose(fact_sensitivity["depth_scale"], 1.0)
                & np.isclose(fact_sensitivity["price_multiplier"], price),
                "purchasers_median",
            ].iloc[0]
            as_fitted = ri == 0
            result = replay_checked(
                f"base response[{ri}] {price}x", sweep_iter, 0.0, response_scenario_names[ri], price, published,
                state_revenue=state_revenue_as_fitted(price) if as_fitted else None,
            )
            if as_fitted:
                replayed_revenue = np.median(result["annual_revenue"])
                published_revenue = fitted_median[round(price, 4)]
                assert abs(replayed_revenue - published_revenue) < 1e-6 * published_revenue, (
                    f"as-fitted {price}x: replayed revenue median {replayed_revenue} != published {published_revenue}"
                )
                segment_rows.append(allocate_to_segments(result))
                if abs(price - current_price) < 1e-9:
                    current_price_runs["base"] = result
            cells.append(summarize_monthly_purchasers(result))
        purchasers_by_month["base"][str(ri)] = cells

    seg_curve = {
        sid: {
            "revenue": [round(float(row["revenue"][s]), 2) for row in segment_rows],
            "purchasers": [round(float(row["purchasers"][s]), 2) for row in segment_rows],
        }
        for s, sid in enumerate(stack_segment_ids)
    }
    assert stack_segment_ids == seg_order, "segment curve order differs from segOrder"

    for key, parquet_scenario in [("expansion", "Expansion"), ("contraction", "Contraction")]:
        cells = []
        for price in scenario_prices:
            published = fact_macro.loc[
                (fact_macro["scenario"] == parquet_scenario) & np.isclose(fact_macro["price"], price),
                "purchasers_median",
            ].iloc[0]
            result = replay_checked(
                f"{key} {price}x", macro_iter, float(macro_shifts[parquet_scenario]), "stronger", price, published
            )
            if abs(price - current_price) < 1e-9:
                current_price_runs[key] = result
            cells.append(summarize_monthly_purchasers(result))
        purchasers_by_month[key] = cells

    # ---- travelers: national forecast from published I-92 actuals ----
    # Each forecast month = the same month a year earlier x year-to-date growth
    # (latest year's months vs. the same months a year before). The outlook tabs
    # scale it by the simulation's own effect on travel volume, and the band
    # applies the simulation's p5/p95 spread in that volume around Baseline.
    i92_monthly = (
        i92.assign(date=pd.to_datetime(dict(year=i92["Year"], month=i92["Month Number"], day=1)))
        .set_index("date")["U.S. Citizen Originating"]
        .sort_index()
    )
    assert i92_monthly.index.is_unique, "duplicate I-92 months"
    last_actual = i92_monthly.index.max()
    ytd = i92_monthly[i92_monthly.index.year == last_actual.year]
    ytd_prior = i92_monthly[
        (i92_monthly.index.year == last_actual.year - 1) & (i92_monthly.index.month <= last_actual.month)
    ]
    assert len(ytd) == len(ytd_prior) == last_actual.month, "I-92 year-to-date months incomplete"
    yoy_growth = float(ytd.sum() / ytd_prior.sum() - 1)
    forecast_months = pd.date_range(last_actual + pd.offsets.MonthBegin(1), periods=FORWARD_MONTHS, freq="MS")
    # Index 0 = January ... 11 = December, so M1 is January on the page.
    forecast_months = sorted(forecast_months, key=lambda m: m.month)
    assert [m.month for m in forecast_months] == list(range(1, 13)), (
        "forecast doesn't cover each calendar month exactly once"
    )
    baseline_forecast = np.array(
        [i92_monthly[m - pd.DateOffset(years=1)] for m in forecast_months], dtype=float
    ) * (1 + yoy_growth)

    base_volume = np.median(current_price_runs["base"]["annual_person_trips"])
    travelers = {"yoy_growth": round(yoy_growth, 6)}
    for key, result in current_price_runs.items():
        volume = result["annual_person_trips"]
        travelers[key] = {
            "median": (baseline_forecast * np.median(volume) / base_volume).round(0).tolist(),
            "p5": (baseline_forecast * np.percentile(volume, 5) / base_volume).round(0).tolist(),
            "p95": (baseline_forecast * np.percentile(volume, 95) / base_volume).round(0).tolist(),
            "outlook_index": round(float(np.median(volume) / base_volume), 4),
        }

    # ---- company scale: the one factor behind every scaled figure ----
    # market_sizing.parquet multiplies revenue per forecast trip (as-fitted
    # median / panel trips) by national addressable trips, so multiplying any
    # model figure by national_trips / panel_trips puts it on the same scale.
    panel_trips = len(panel["trip_ids"])
    scale_factor = i92_trips * MARKET_SHARE / panel_trips
    for _, row in market_sizing_df.iterrows():
        p = round(float(row["Price Multiplier"]), 4)
        assert abs(fitted_median[p] * scale_factor - row["Scaled Annual Revenue"]) < 1.0, (
            f"scale factor doesn't reproduce market_sizing's scaled revenue at {p}x"
        )
    assert np.allclose(
        sensitivity_cells["0_0"]["revenue_median"], portfolio["as fitted"]["revenue_median"]
    ), "sensitivity cell 0_0 differs from the as-fitted sweep, so scaled charts won't match the company-scale card"

    payload = {
        "meta": {
            "run_id": run_id,
            "current_price": current_price,
            "recommended_price": recommended_price,
            "purchasers_available": True,
            "segment_purchasers_available": True,
            "eligible_accounts": eligible_accounts,
            "response_scale_joint_sensitivity": round(
                float(assumption_values.get("response scale (joint sensitivity)")), 4
            ),
            "depth_scale_joint_sensitivity": round(
                float(assumption_values.get("depth scale (joint sensitivity)")), 4
            ),
            "scale_factor": scale_factor,
            "panel_trips": panel_trips,
        },
        "grid": [round(g, 4) for g in grid],
        "portfolio": portfolio,
        "scenarios": scenarios,
        "segOrder": seg_order,
        "segMeta": seg_meta,
        "segCurve": seg_curve,
        "dormant": dormant,
        "probCurve": prob_curve,
        "sensitivityGrid": sensitivity_grid_payload,
        "travelers": travelers,
        "purchasersByMonth": purchasers_by_month,
        "marketSizing": {
            "meta": {
                "i92_year": i92_year,
                "i92_trips": round(i92_trips, 0),
                "market_share": MARKET_SHARE,
                "national_trips": round(i92_trips * MARKET_SHARE, 0),
                "target": 100_000_000,
            },
            "byPrice": market_sizing_payload,
        },
    }

    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
