"""
Monte Carlo DCF for Restaurant Brands International (QSR).

This script now reads all valuation assumptions from valuation_premises.json
and publishes auditable targets for the hybrid LSTM workflow.
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from valuation.valuation_utils import (
    build_anchor_dataframe,
    build_price_targets,
    compute_ke_base,
    compute_wacc_base,
    dcf_price,
    get_operating_assumptions,
    load_valuation_premises,
    save_anchor_dataframe,
    save_targets,
)

warnings.filterwarnings("ignore")

np.random.seed(42)

OUTPUTS_DIR = ROOT_DIR / "outputs"
FIGURES_DIR = ROOT_DIR / "figures"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

PREMISES = load_valuation_premises()
OPS = get_operating_assumptions(PREMISES)
CURRENT_PRICE = float(PREMISES["current_price"])
FORECAST_DAYS = int(PREMISES["forecast_days"])

REV_GROWTH_BASE = OPS["rev_growth_base"]
EBIT_MARGIN_BASE = OPS["ebit_margin_base"]
DA_PCT_BASE = OPS["da_pct_base"]
CAPEX_PCT_BASE = OPS["capex_pct_base"]
NWC_PCT_BASE = OPS["nwc_pct_base"]
G_TERMINAL = float(OPS["g_terminal"])
WACC_BASE = float(compute_wacc_base(PREMISES))
KE_BASE = float(compute_ke_base(PREMISES))

MC_CFG = PREMISES["montecarlo"]
N_SIM = int(os.environ.get("MONTECARLO_N_SIM", MC_CFG["n_sim_default"]))
RG_STD = float(MC_CFG["rev_growth_std"])
EM_STD = float(MC_CFG["ebit_margin_std"])
WACC_STD = float(MC_CFG["wacc_std"])
G_MIN = float(MC_CFG["g_terminal_min"])
G_MODE = float(MC_CFG["g_terminal_mode"])
G_MAX = float(MC_CFG["g_terminal_max"])


prices: list[float] = []
diagnostics: list[dict[str, float]] = []

for _ in range(N_SIM):
    rg = np.clip(np.random.normal(REV_GROWTH_BASE, RG_STD), 0.01, 0.12)
    em = np.clip(np.random.normal(EBIT_MARGIN_BASE, EM_STD), 0.24, 0.42)
    wacc = np.clip(np.random.normal(WACC_BASE, WACC_STD), 0.055, 0.14)
    g = float(np.random.triangular(G_MIN, G_MODE, G_MAX))
    if wacc <= g:
        wacc = g + 0.02

    price = dcf_price(
        premises=PREMISES,
        rev_grow=rg,
        ebit_margins=em,
        da_pct=DA_PCT_BASE,
        capex_pct=CAPEX_PCT_BASE,
        nwc_pct=NWC_PCT_BASE,
        wacc=wacc,
        g=g,
    )
    prices.append(price)
    diagnostics.append(
        {
            "wacc": float(wacc),
            "g_terminal": float(g),
            "rev_grow_avg": float(np.mean(rg)),
            "ebit_margin_avg": float(np.mean(em)),
        }
    )

prices_arr = np.asarray(prices, dtype=np.float64)
diag_df = pd.DataFrame(diagnostics)

pct_labels = [5, 10, 25, 50, 75, 90, 95]
pcts = {p: float(np.percentile(prices_arr, p)) for p in pct_labels}
bear = pcts[10]
base = pcts[50]
bull = pcts[90]
mean_ = float(np.mean(prices_arr))
std_ = float(np.std(prices_arr))
prob_upside = float(np.mean(prices_arr > CURRENT_PRICE) * 100.0)

targets = build_price_targets(PREMISES, simulated_prices=prices_arr)
targets_path = save_targets(targets)
anchor_df = build_anchor_dataframe(targets)
anchor_path = save_anchor_dataframe(anchor_df)

print("=" * 62)
print("  MONTE CARLO DCF - Restaurant Brands Intl (QSR)")
print("=" * 62)
print(f"  Premises version      : {PREMISES['version']}")
print(f"  Number of simulations : {N_SIM:,}")
print(f"  Current price         : USD {CURRENT_PRICE:.2f}")
print(f"  WACC base             : {WACC_BASE * 100:.2f}%")
print(f"  Ke base               : {KE_BASE * 100:.2f}%")
print()
print("  TARGET PRICE DISTRIBUTION (USD/share)")
print("  " + "-" * 46)
for pct in pct_labels:
    upside = (pcts[pct] / CURRENT_PRICE - 1.0) * 100.0
    mark = " <-- CURRENT" if abs(pcts[pct] - CURRENT_PRICE) < 3.0 else ""
    print(f"  Percentile {pct:3d}% : USD {pcts[pct]:7.2f}   ({upside:+.1f}%){mark}")
print()
print(f"  Mean          : USD {mean_:7.2f}   ({(mean_ / CURRENT_PRICE - 1.0) * 100:+.1f}%)")
print(f"  Std dev       : USD {std_:7.2f}")
print()
print("  SCENARIOS")
print(f"  Bear (P10)    : USD {bear:7.2f}   ({(bear / CURRENT_PRICE - 1.0) * 100:+.1f}%)")
print(f"  Base (P50)    : USD {base:7.2f}   ({(base / CURRENT_PRICE - 1.0) * 100:+.1f}%)")
print(f"  Bull (P90)    : USD {bull:7.2f}   ({(bull / CURRENT_PRICE - 1.0) * 100:+.1f}%)")
print()
print(f"  P(price > current) = {prob_upside:.1f}%")
if targets.get("summary_targets"):
    print(
        "  Summary anchor targets : "
        f"USD {targets['summary_targets']['bear_target_price']:.2f} / "
        f"USD {targets['summary_targets']['base_target_price']:.2f} / "
        f"USD {targets['summary_targets']['bull_target_price']:.2f}"
    )
print(f"  Targets JSON saved  : {targets_path}")
print(f"  Anchor CSV saved    : {anchor_path}")
print("=" * 62)

csv_path = OUTPUTS_DIR / "monte_carlo_simulations.csv"
pd.DataFrame(
    {
        "preco_simulado": prices_arr,
        "wacc": diag_df["wacc"],
        "g_terminal": diag_df["g_terminal"],
        "rev_grow_avg": diag_df["rev_grow_avg"],
        "ebit_margin_avg": diag_df["ebit_margin_avg"],
    }
).to_csv(csv_path, index=False)
print(f"\n  CSV saved: {csv_path}")


fig, ax = plt.subplots(figsize=(13, 7))
fig.patch.set_facecolor("#FFFFFF")
ax.set_facecolor("#FFFFFF")

zones = [
    (prices_arr[prices_arr < bear], "#C30D1A", "Bear (< P10)"),
    (prices_arr[(prices_arr >= bear) & (prices_arr < base)], "#E67E22", "Below Base (P10-P50)"),
    (prices_arr[(prices_arr >= base) & (prices_arr <= bull)], "#F1C40F", "Base (P50-P90)"),
    (prices_arr[prices_arr > bull], "#2C3E50", "Bull (> P90)"),
]

bins = np.linspace(prices_arr.min(), min(prices_arr.max(), 300.0), 80)
for zone_prices, color, label in zones:
    if len(zone_prices) == 0:
        continue
    ax.hist(
        zone_prices,
        bins=bins,
        color=color,
        alpha=0.9,
        label=label,
        edgecolor="#C8102E",
        linewidth=0.5,
    )

ax.axvline(CURRENT_PRICE, color="#000000", lw=2, ls="--", label=f"Current Price: USD {CURRENT_PRICE:.2f}", zorder=10)
ax.axvline(base, color="#E67E22", lw=2, ls="-.", label=f"Base (P50): USD {base:.2f}", zorder=10)
ax.axvline(bear, color="#C30D1A", lw=1.5, ls=":", label=f"Bear (P10): USD {bear:.2f}", zorder=10)
ax.axvline(bull, color="#2C3E50", lw=1.5, ls=":", label=f"Bull (P90): USD {bull:.2f}", zorder=10)

for value, label, color, y_pos in [
    (CURRENT_PRICE, f"Current\nUSD {CURRENT_PRICE:.0f}", "#000000", 0.90),
    (base, f"Base\nUSD {base:.0f}", "#D35400", 0.75),
    (bear, f"Bear\nUSD {bear:.0f}", "#C30D1A", 0.72),
    (bull, f"Bull\nUSD {bull:.0f}", "#2C3E50", 0.72),
]:
    ax.annotate(
        label,
        xy=(value, 0),
        xytext=(value + 2.0, ax.get_ylim()[1] * y_pos),
        color=color,
        fontsize=9,
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=color, lw=1.2),
        ha="left",
        va="top",
        bbox=dict(facecolor="#FFFFFF", edgecolor=color, boxstyle="round,pad=0.2", alpha=0.8),
    )

ax.set_xlabel("Target price per share (USD)", color="#333333", fontsize=12)
ax.set_ylabel("Frequency (# of simulations)", color="#333333", fontsize=12)
ax.set_title(
    f"Monte Carlo Simulation - DCF RBI/QSR  |  N={N_SIM:,} runs\n"
    f"Structured premises v{PREMISES['version']}  |  Forecast horizon: {FORECAST_DAYS} business days",
    color="#8B0000",
    fontsize=14,
    fontweight="bold",
    pad=15,
)
ax.tick_params(colors="#333333", labelsize=10)
for spine in ax.spines.values():
    spine.set_color("#CCCCCC")

ax.legend(framealpha=0.9, labelcolor="#333333", fontsize=9, loc="upper right", facecolor="#FFFFFF", edgecolor="#CCCCCC")
stats_text = (
    f"Current: USD {CURRENT_PRICE:.2f}\n"
    f"P5: USD {pcts[5]:.2f}  |  P95: USD {pcts[95]:.2f}\n"
    f"P25: USD {pcts[25]:.2f}  |  P75: USD {pcts[75]:.2f}\n"
    f"Mean: USD {mean_:.2f}  |  Std: USD {std_:.2f}\n"
    f"P(Upside): {prob_upside:.1f}%"
)
ax.text(
    0.02,
    0.98,
    stats_text,
    transform=ax.transAxes,
    fontsize=9,
    color="#333333",
    va="top",
    bbox=dict(boxstyle="round,pad=0.5", facecolor="#FFFFFF", edgecolor="#CCCCCC", alpha=0.9),
)

plt.tight_layout()
hist_path = FIGURES_DIR / "monte_carlo_distribution.png"
plt.savefig(hist_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"  Histogram saved: {hist_path}")


def one_way_sensitivity(label: str, lo_val: float, hi_val: float) -> tuple[float, float, float]:
    base_price_value = dcf_price(
        premises=PREMISES,
        rev_grow=REV_GROWTH_BASE,
        ebit_margins=EBIT_MARGIN_BASE,
        da_pct=DA_PCT_BASE,
        capex_pct=CAPEX_PCT_BASE,
        nwc_pct=NWC_PCT_BASE,
        wacc=WACC_BASE,
        g=G_TERMINAL,
    )

    if label == "WACC":
        p_lo = dcf_price(PREMISES, REV_GROWTH_BASE, EBIT_MARGIN_BASE, DA_PCT_BASE, CAPEX_PCT_BASE, NWC_PCT_BASE, lo_val, G_TERMINAL)
        p_hi = dcf_price(PREMISES, REV_GROWTH_BASE, EBIT_MARGIN_BASE, DA_PCT_BASE, CAPEX_PCT_BASE, NWC_PCT_BASE, hi_val, G_TERMINAL)
    elif label == "g terminal":
        p_lo = dcf_price(PREMISES, REV_GROWTH_BASE, EBIT_MARGIN_BASE, DA_PCT_BASE, CAPEX_PCT_BASE, NWC_PCT_BASE, WACC_BASE, lo_val)
        p_hi = dcf_price(PREMISES, REV_GROWTH_BASE, EBIT_MARGIN_BASE, DA_PCT_BASE, CAPEX_PCT_BASE, NWC_PCT_BASE, WACC_BASE, hi_val)
    elif label == "Rev. Growth":
        p_lo = dcf_price(PREMISES, REV_GROWTH_BASE + lo_val, EBIT_MARGIN_BASE, DA_PCT_BASE, CAPEX_PCT_BASE, NWC_PCT_BASE, WACC_BASE, G_TERMINAL)
        p_hi = dcf_price(PREMISES, REV_GROWTH_BASE + hi_val, EBIT_MARGIN_BASE, DA_PCT_BASE, CAPEX_PCT_BASE, NWC_PCT_BASE, WACC_BASE, G_TERMINAL)
    elif label == "EBIT Margin":
        p_lo = dcf_price(PREMISES, REV_GROWTH_BASE, EBIT_MARGIN_BASE + lo_val, DA_PCT_BASE, CAPEX_PCT_BASE, NWC_PCT_BASE, WACC_BASE, G_TERMINAL)
        p_hi = dcf_price(PREMISES, REV_GROWTH_BASE, EBIT_MARGIN_BASE + hi_val, DA_PCT_BASE, CAPEX_PCT_BASE, NWC_PCT_BASE, WACC_BASE, G_TERMINAL)
    elif label == "CAPEX %":
        p_lo = dcf_price(PREMISES, REV_GROWTH_BASE, EBIT_MARGIN_BASE, DA_PCT_BASE, CAPEX_PCT_BASE + lo_val, NWC_PCT_BASE, WACC_BASE, G_TERMINAL)
        p_hi = dcf_price(PREMISES, REV_GROWTH_BASE, EBIT_MARGIN_BASE, DA_PCT_BASE, CAPEX_PCT_BASE + hi_val, NWC_PCT_BASE, WACC_BASE, G_TERMINAL)
    elif label == "D&A %":
        p_lo = dcf_price(PREMISES, REV_GROWTH_BASE, EBIT_MARGIN_BASE, DA_PCT_BASE + lo_val, CAPEX_PCT_BASE, NWC_PCT_BASE, WACC_BASE, G_TERMINAL)
        p_hi = dcf_price(PREMISES, REV_GROWTH_BASE, EBIT_MARGIN_BASE, DA_PCT_BASE + hi_val, CAPEX_PCT_BASE, NWC_PCT_BASE, WACC_BASE, G_TERMINAL)
    else:
        p_lo = base_price_value
        p_hi = base_price_value

    return float(base_price_value), float(p_lo), float(p_hi)


tornado_params = [
    ("WACC", WACC_BASE - 0.02, WACC_BASE + 0.02, "+/-2pp"),
    ("g terminal", 0.015, 0.035, "1.5% to 3.5%"),
    ("EBIT Margin", -0.03, 0.03, "+/-3pp"),
    ("Rev. Growth", -0.02, 0.02, "+/-2pp"),
    ("CAPEX %", 0.01, -0.01, "+/-1pp"),
    ("D&A %", -0.01, 0.01, "+/-1pp"),
]

tornado_rows = []
for label, lo, hi, unit in tornado_params:
    p_base, p_lo, p_hi = one_way_sensitivity(label, lo, hi)
    tornado_rows.append(
        {
            "label": f"{label} ({unit})",
            "base": p_base,
            "lo": min(p_lo, p_hi),
            "hi": max(p_lo, p_hi),
            "span": abs(p_hi - p_lo),
        }
    )

tornado_rows.sort(key=lambda row: row["span"])

fig2, ax2 = plt.subplots(figsize=(13, 7))
fig2.patch.set_facecolor("#FFFFFF")
ax2.set_facecolor("#FFFFFF")

p_base_t = tornado_rows[0]["base"]
for row_index, row in enumerate(tornado_rows):
    lo_delta = row["lo"] - p_base_t
    hi_delta = row["hi"] - p_base_t
    ax2.barh(row_index, lo_delta, left=p_base_t, color="#95A5A6", alpha=0.9, height=0.6, edgecolor="#C8102E")
    ax2.barh(row_index, hi_delta, left=p_base_t, color="#C30D1A", alpha=0.9, height=0.6, edgecolor="#C8102E")
    ax2.text(row["hi"] + 0.5, row_index, f"USD {row['hi']:.1f}", va="center", color="#C30D1A", fontsize=9, fontweight="bold")
    ax2.text(row["lo"] - 0.5, row_index, f"USD {row['lo']:.1f}", va="center", color="#7F8C8D", fontsize=9, fontweight="bold", ha="right")

ax2.axvline(p_base_t, color="#333333", lw=1.5, ls="--", zorder=10, label=f"Base: USD {p_base_t:.2f}")
ax2.axvline(CURRENT_PRICE, color="#F39C12", lw=1.5, ls=":", label=f"Current Price: USD {CURRENT_PRICE:.2f}")
ax2.set_yticks(range(len(tornado_rows)))
ax2.set_yticklabels([row["label"] for row in tornado_rows], color="#333333", fontsize=11, fontweight="bold")
ax2.set_xlabel("Target price per share (USD)", color="#333333", fontsize=11)
ax2.set_title(
    "Sensitivity Analysis - Tornado Chart  |  DCF RBI/QSR\n"
    "One-way variation of each parameter vs. the structured base case",
    color="#8B0000",
    fontsize=14,
    fontweight="bold",
    pad=15,
)
ax2.tick_params(colors="#333333")
for spine in ax2.spines.values():
    spine.set_color("#CCCCCC")

low_patch = mpatches.Patch(color="#95A5A6", alpha=0.9, label="Bear case")
high_patch = mpatches.Patch(color="#C30D1A", alpha=0.9, label="Bull case")
ax2.legend(handles=[high_patch, low_patch], framealpha=0.9, labelcolor="#333333", fontsize=10, loc="lower right", facecolor="#FFFFFF", edgecolor="#CCCCCC")

plt.tight_layout()
tornado_path = FIGURES_DIR / "tornado_sensitivity.png"
plt.savefig(tornado_path, dpi=150, bbox_inches="tight", facecolor=fig2.get_facecolor())
plt.close()
print(f"  Tornado saved: {tornado_path}")
print("\nMonte Carlo valuation completed successfully.")
