from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
FIGURES_DIR = ROOT_DIR / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def save_irr_heatmap() -> Path:
    x_labels = ["9.5x", "11.0x", "12.5x", "14.0x", "15.5x", "17.0x", "18.5x"]
    y_labels = ["12.1%", "15.1%", "18.1%", "21.1%", "24.1%", "27.1%", "30.1%"]
    data = np.array(
        [
            [6, 9, 11, 14, 16, 18, 19],
            [9, 12, 15, 17, 19, 21, 23],
            [12, 15, 18, 20, 22, 24, 26],
            [15, 18, 21, 23, 26, 28, 30],
            [18, 21, 24, 27, 29, 31, 33],
            [21, 24, 27, 30, 33, 35, 37],
            [24, 28, 31, 33, 36, 38, 41],
        ]
    )
    df = pd.DataFrame(data, index=y_labels, columns=x_labels)

    cmap = mcolors.LinearSegmentedColormap.from_list(
        "irr_heatmap",
        ["#F25C54", "#F39C12", "#F1C40F", "#A9DFBF", "#52BE80"],
    )

    fig, ax = plt.subplots(figsize=(10, 6), facecolor="#FFFFFF")
    sns.heatmap(
        df,
        annot=True,
        fmt="d",
        cmap=cmap,
        cbar=False,
        linewidths=1,
        linecolor="#FFFFFF",
        ax=ax,
        annot_kws={"fontsize": 12, "weight": "bold", "color": "#333333"},
    )
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_xlabel("5y Exit P/E fwd 1y", fontsize=13, color="#333333", labelpad=15)
    ax.set_ylabel("Net income CAGR (2024-2030E)", fontsize=13, color="#333333", labelpad=15)
    plt.xticks(fontsize=12, color="#333333", fontweight="bold")
    plt.yticks(fontsize=12, color="#333333", fontweight="bold", rotation=0)
    plt.text(0, -1.2, "Sensitivity analysis reinforces the return profile", fontsize=18, color="#2C3E50", ha="left")
    plt.text(0, -0.6, "IRR Sensitivity Analysis [% ; x]", fontsize=12, color="#7F8C8D", style="italic", ha="left")
    plt.text(
        -0.6,
        0.45,
        "Nominal IRR:\n23.4%",
        fontsize=10,
        color="#333333",
        fontweight="bold",
        ha="center",
        va="center",
        bbox=dict(facecolor="#BDC3C7", alpha=0.5, boxstyle="square,pad=0.6", edgecolor="none"),
    )
    plt.tight_layout()

    out_path = FIGURES_DIR / "irr_heatmap.png"
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    return out_path


def save_target_price_heatmap() -> Path:
    p_wacc = ["7.5%", "8.0%", "8.5%", "9.0%", "9.5%"]
    p_g = ["1.5%", "2.0%", "2.5%", "3.0%", "3.5%"]
    target_price_data = np.array(
        [
            [105, 95, 87, 81, 75],
            [112, 100, 91, 84, 78],
            [120, 107, 96, 88, 82],
            [130, 115, 102, 93, 85],
            [142, 124, 109, 98, 90],
        ]
    )
    df = pd.DataFrame(target_price_data, index=p_g, columns=p_wacc)

    fig, ax = plt.subplots(figsize=(9, 5), facecolor="#FFFFFF")
    sns.heatmap(
        df,
        annot=True,
        fmt="d",
        cmap="RdYlGn",
        cbar=False,
        linewidths=1,
        linecolor="#FFFFFF",
        ax=ax,
        annot_kws={"fontsize": 12, "weight": "bold", "color": "#333333"},
    )
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_xlabel("WACC", fontsize=13, color="#333333", labelpad=15)
    ax.set_ylabel("Perpetuity Growth (g)", fontsize=13, color="#333333", labelpad=15)
    plt.xticks(fontsize=12, color="#333333", fontweight="bold")
    plt.yticks(fontsize=12, color="#333333", fontweight="bold", rotation=0)
    plt.text(0, -0.8, "Target Price Sensitivity Analysis [% ; USD]", fontsize=14, color="#C8102E", fontweight="bold", ha="left")
    plt.tight_layout()

    out_path = FIGURES_DIR / "target_price_heatmap.png"
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    irr_path = save_irr_heatmap()
    target_path = save_target_price_heatmap()
    print(f"Saved: {irr_path}")
    print(f"Saved: {target_path}")
