from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


VALUATION_DIR = Path(__file__).resolve().parent
ROOT_DIR = VALUATION_DIR.parent
DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
OUTPUTS_DIR = ROOT_DIR / "outputs"
FIGURES_DIR = ROOT_DIR / "figures"

PREMISES_PATH = DATA_PROCESSED_DIR / "valuation_premises.json"
TARGETS_PATH = DATA_PROCESSED_DIR / "valuation_targets.json"
ANCHOR_PATH = DATA_PROCESSED_DIR / "valuation_anchor.csv"
MONTECARLO_CSV_PATH = OUTPUTS_DIR / "monte_carlo_simulations.csv"


def load_valuation_premises(path: Path | None = None) -> dict[str, Any]:
    payload = json.loads((path or PREMISES_PATH).read_text(encoding="utf-8"))
    return payload


def get_capital_structure(premises: dict[str, Any]) -> dict[str, float]:
    capital = premises["capital_structure"]
    return {key: float(value) for key, value in capital.items()}


def get_operating_assumptions(premises: dict[str, Any]) -> dict[str, Any]:
    ops = premises["operating_assumptions"]
    return {
        "n_years": int(ops["n_years"]),
        "g_terminal": float(ops["g_terminal"]),
        "rev_growth_base": np.array(ops["rev_growth_base"], dtype=np.float64),
        "ebit_margin_base": np.array(ops["ebit_margin_base"], dtype=np.float64),
        "da_pct_base": np.array(ops["da_pct_base"], dtype=np.float64),
        "capex_pct_base": np.array(ops["capex_pct_base"], dtype=np.float64),
        "nwc_pct_base": np.array(ops["nwc_pct_base"], dtype=np.float64),
    }


def get_summary_targets(premises: dict[str, Any]) -> dict[str, float] | None:
    summary = premises.get("valuation_summary")
    if not isinstance(summary, dict):
        return None
    required = ("base_target_price", "bear_target_price", "bull_target_price")
    if not all(key in summary for key in required):
        return None
    return {
        "base_target_price": float(summary["base_target_price"]),
        "bear_target_price": float(summary["bear_target_price"]),
        "bull_target_price": float(summary["bull_target_price"]),
        "base_ke": float(summary.get("base_ke", compute_ke_base(premises))),
    }


def compute_ke_base(premises: dict[str, Any]) -> float:
    capital = get_capital_structure(premises)
    return capital["rf"] + capital["beta"] * capital["erp"]


def compute_wacc_base(premises: dict[str, Any]) -> float:
    capital = get_capital_structure(premises)
    kd_net = capital["cost_debt"] * (1.0 - capital["tax_rate"])
    return capital["equity_ratio"] * compute_ke_base(premises) + capital["debt_ratio"] * kd_net


def dcf_price(
    premises: dict[str, Any],
    rev_grow: np.ndarray,
    ebit_margins: np.ndarray,
    da_pct: np.ndarray,
    capex_pct: np.ndarray,
    nwc_pct: np.ndarray,
    wacc: float,
    g: float,
) -> float:
    capital = get_capital_structure(premises)
    rev = float(premises["base_revenue"])
    fcffs: list[float] = []

    for index in range(int(premises["operating_assumptions"]["n_years"])):
        rev = rev * (1.0 + float(rev_grow[index]))
        ebit = rev * float(ebit_margins[index])
        nopat = ebit * (1.0 - capital["tax_rate"])
        da = rev * float(da_pct[index])
        capex = rev * float(capex_pct[index])
        nwc = rev * float(nwc_pct[index])
        fcffs.append(nopat + da - capex - nwc)

    tv = fcffs[-1] * (1.0 + g) / max(wacc - g, 1e-6)
    pv_fcff = sum(value / (1.0 + wacc) ** (offset + 1) for offset, value in enumerate(fcffs))
    pv_tv = tv / (1.0 + wacc) ** len(fcffs)
    ev = pv_fcff + pv_tv
    equity = ev - capital["total_debt"] + capital["cash"]
    return equity / float(premises["shares_out"])


def base_case_price(premises: dict[str, Any]) -> float:
    ops = get_operating_assumptions(premises)
    return dcf_price(
        premises=premises,
        rev_grow=ops["rev_growth_base"],
        ebit_margins=ops["ebit_margin_base"],
        da_pct=ops["da_pct_base"],
        capex_pct=ops["capex_pct_base"],
        nwc_pct=ops["nwc_pct_base"],
        wacc=compute_wacc_base(premises),
        g=ops["g_terminal"],
    )


def scenario_price(premises: dict[str, Any], scenario_name: str) -> float:
    shocks = premises["scenario_shocks"][scenario_name]
    ops = get_operating_assumptions(premises)

    rev_grow = np.clip(ops["rev_growth_base"] + float(shocks["rev_growth_delta"]), 0.005, 0.15)
    ebit_margin = np.clip(ops["ebit_margin_base"] + float(shocks["ebit_margin_delta"]), 0.18, 0.45)
    da_pct = np.clip(ops["da_pct_base"] + float(shocks["da_pct_delta"]), 0.03, 0.12)
    capex_pct = np.clip(ops["capex_pct_base"] + float(shocks["capex_pct_delta"]), 0.02, 0.08)
    nwc_pct = np.clip(ops["nwc_pct_base"] + float(shocks["nwc_pct_delta"]), -0.01, 0.02)
    wacc = np.clip(compute_wacc_base(premises) + float(shocks["wacc_delta"]), 0.05, 0.15)
    g_terminal = np.clip(ops["g_terminal"] + float(shocks["g_terminal_delta"]), 0.005, 0.04)
    if wacc <= g_terminal:
        wacc = g_terminal + 0.02

    return dcf_price(
        premises=premises,
        rev_grow=rev_grow,
        ebit_margins=ebit_margin,
        da_pct=da_pct,
        capex_pct=capex_pct,
        nwc_pct=nwc_pct,
        wacc=wacc,
        g=g_terminal,
    )


def build_price_targets(
    premises: dict[str, Any],
    simulated_prices: np.ndarray | None = None,
    percentiles: dict[str, float] | None = None,
) -> dict[str, Any]:
    current_price = float(premises["current_price"])
    base_dcf = float(base_case_price(premises))
    forecast_days = int(premises["forecast_days"])
    summary_targets = get_summary_targets(premises)

    if simulated_prices is not None and len(simulated_prices) > 0:
        prices = np.asarray(simulated_prices, dtype=np.float64)
        pct_map = {
            "p5": float(np.percentile(prices, 5)),
            "p10": float(np.percentile(prices, 10)),
            "p25": float(np.percentile(prices, 25)),
            "p50": float(np.percentile(prices, 50)),
            "p75": float(np.percentile(prices, 75)),
            "p90": float(np.percentile(prices, 90)),
            "p95": float(np.percentile(prices, 95)),
        }
        if summary_targets:
            source = "summary_grid_with_montecarlo_distribution"
            bear_price = summary_targets["bear_target_price"]
            base_price = summary_targets["base_target_price"]
            bull_price = summary_targets["bull_target_price"]
        else:
            source = "montecarlo_percentiles"
            bear_price = pct_map["p10"]
            base_price = pct_map["p50"]
            bull_price = pct_map["p90"]
    else:
        pct_map = percentiles or {}
        if summary_targets:
            source = "summary_grid"
            bear_price = summary_targets["bear_target_price"]
            base_price = summary_targets["base_target_price"]
            bull_price = summary_targets["bull_target_price"]
        else:
            source = "deterministic_scenarios"
            bear_price = float(scenario_price(premises, "bear"))
            base_price = base_dcf
            bull_price = float(scenario_price(premises, "bull"))

    ordered = sorted([bear_price, base_price, bull_price])
    bear_price, base_price, bull_price = ordered

    return {
        "premises_version": premises["version"],
        "ticker": premises["ticker"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "forecast_days": forecast_days,
        "current_price": current_price,
        "base_case_dcf_price": base_dcf,
        "bear_price": float(bear_price),
        "base_price": float(base_price),
        "bull_price": float(bull_price),
        "percentiles": pct_map,
        "summary_targets": summary_targets,
        "ke_base": float(compute_ke_base(premises)),
        "wacc_base": float(compute_wacc_base(premises)),
    }


def build_anchor_curve(start_price: float, target_price: float, periods: int) -> np.ndarray:
    if periods <= 0:
        return np.zeros(0, dtype=np.float64)
    if start_price <= 0 or target_price <= 0:
        return np.linspace(start_price, target_price, periods, dtype=np.float64)

    ratio = (target_price / start_price) ** (1.0 / periods)
    steps = np.arange(1, periods + 1, dtype=np.float64)
    return start_price * np.power(ratio, steps)


def build_anchor_dataframe(targets: dict[str, Any], start_price: float | None = None) -> pd.DataFrame:
    current_price = float(start_price if start_price is not None else targets["current_price"])
    forecast_days = int(targets["forecast_days"])
    return pd.DataFrame(
        {
            "step": np.arange(1, forecast_days + 1, dtype=np.int32),
            "anchor_base": build_anchor_curve(current_price, float(targets["base_price"]), forecast_days),
            "anchor_bear": build_anchor_curve(current_price, float(targets["bear_price"]), forecast_days),
            "anchor_bull": build_anchor_curve(current_price, float(targets["bull_price"]), forecast_days),
        }
    )


def save_targets(targets: dict[str, Any], path: Path | None = None) -> Path:
    target_path = path or TARGETS_PATH
    target_path.write_text(json.dumps(targets, indent=2), encoding="utf-8")
    return target_path


def save_anchor_dataframe(df: pd.DataFrame, path: Path | None = None) -> Path:
    target_path = path or ANCHOR_PATH
    df.to_csv(target_path, index=False)
    return target_path


def load_cached_targets(path: Path | None = None) -> dict[str, Any] | None:
    target_path = path or TARGETS_PATH
    if not target_path.exists():
        return None
    return json.loads(target_path.read_text(encoding="utf-8"))


def load_or_build_targets(
    premises: dict[str, Any],
    targets_path: Path | None = None,
    montecarlo_csv_path: Path | None = None,
) -> dict[str, Any]:
    target_path = targets_path or TARGETS_PATH
    cached = load_cached_targets(target_path)
    if cached and cached.get("premises_version") == premises.get("version"):
        return cached

    simulation_path = montecarlo_csv_path or MONTECARLO_CSV_PATH
    if simulation_path.exists():
        mc_df = pd.read_csv(simulation_path, usecols=["preco_simulado"])
        targets = build_price_targets(premises, simulated_prices=mc_df["preco_simulado"].to_numpy())
        save_targets(targets, target_path)
        save_anchor_dataframe(build_anchor_dataframe(targets), ANCHOR_PATH)
        return targets

    targets = build_price_targets(premises)
    save_targets(targets, target_path)
    save_anchor_dataframe(build_anchor_dataframe(targets), ANCHOR_PATH)
    return targets
