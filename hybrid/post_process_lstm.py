from __future__ import annotations

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

from valuation.valuation_utils import load_or_build_targets, load_valuation_premises


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
OUTPUTS_DIR = ROOT_DIR / "outputs"
FIGURES_DIR = ROOT_DIR / "figures"
RES_PATH = OUTPUTS_DIR / "hybrid_forecast.csv"
OUT_PATH = FIGURES_DIR / "hybrid_scenario_sensitivity.png"

premises = load_valuation_premises()
targets = load_or_build_targets(premises)
df_res = pd.read_csv(RES_PATH, parse_dates=["data"])

required = {
    "preco_hibrido_base",
    "preco_hibrido_bear",
    "preco_hibrido_bull",
    "intervalo_lo",
    "intervalo_hi",
}
missing = sorted(required.difference(df_res.columns))
if missing:
    raise RuntimeError(
        "outputs/hybrid_forecast.csv does not contain the required hybrid columns. "
        f"Missing: {', '.join(missing)}"
    )

raw = yf.download(
    premises["ticker"],
    start=premises.get("plot_history_start", "2025-01-01"),
    end=(pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
    auto_adjust=True,
    progress=False,
    threads=False,
)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
hist = raw[["Close"]].copy().dropna()

fig, ax = plt.subplots(figsize=(16, 9))
fig.patch.set_facecolor("#FFFFFF")
ax.set_facecolor("#FFFFFF")

ax.plot(hist.index, hist["Close"], color="#4A4A4A", lw=1.8, label="Real price history")
ax.plot(df_res["data"], df_res["preco_hibrido_bull"], color="#148F77", lw=1.8, ls="--", label=f"Hybrid bull: USD {df_res['preco_hibrido_bull'].iloc[-1]:.2f}")
ax.plot(df_res["data"], df_res["preco_hibrido_base"], color="#F4B41A", lw=2.6, label=f"Hybrid base: USD {df_res['preco_hibrido_base'].iloc[-1]:.2f}")
ax.plot(df_res["data"], df_res["preco_hibrido_bear"], color="#C30D1A", lw=1.8, ls="--", label=f"Hybrid bear: USD {df_res['preco_hibrido_bear'].iloc[-1]:.2f}")
ax.fill_between(
    df_res["data"],
    df_res["intervalo_lo"],
    df_res["intervalo_hi"],
    color="#F4B41A",
    alpha=0.12,
    label="Hybrid 95% CI",
)
ax.axhline(targets["current_price"], color="#000000", lw=1.5, ls=":", alpha=0.7, label=f"Current price: USD {targets['current_price']:.2f}")

ax.set_xlabel("Date", color="#333333", fontsize=12)
ax.set_ylabel("Price (USD)", color="#333333", fontsize=12)
ax.set_title(
    "Hybrid LSTM scenario sensitivity\nProjected paths under bear, base, and bull valuation anchors",
    color="#C8102E",
    fontsize=15,
    fontweight="bold",
    pad=15,
)
ax.tick_params(colors="#333333")
for spine in ax.spines.values():
    spine.set_color("#CCCCCC")
ax.legend(framealpha=0.92, labelcolor="#333333", fontsize=10, loc="upper left", facecolor="#FFFFFF", edgecolor="#CCCCCC")

box_txt = (
    f"Valuation source: {targets['source']}\n"
    f"Bear/Base/Bull: {targets['bear_price']:.2f} / {targets['base_price']:.2f} / {targets['bull_price']:.2f}"
)
ax.text(
    0.99,
    0.03,
    box_txt,
    transform=ax.transAxes,
    fontsize=10,
    color="#333333",
    va="bottom",
    ha="right",
    bbox=dict(boxstyle="round,pad=0.5", facecolor="#FFFFFF", edgecolor="#CCCCCC", alpha=0.9),
)

plt.tight_layout()
plt.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
plt.close()

print(f"Sensitivity chart saved: {OUT_PATH}")
