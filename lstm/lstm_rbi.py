"""
=============================================================================
  LSTM — Previsão de Preço  Restaurant Brands International Inc. (QSR)
  Implementado com PyTorch (compatível com Python 3.14)
  Inspirado em arthur1535/LSTM, adaptado com features adicionais para QSR
=============================================================================

Dependências (já instaladas):
  torch, numpy, pandas, yfinance, matplotlib, scikit-learn

Resultados:
  lstm_previsao.png   -> historico + previsao 12 meses + bandas MC
  lstm_metricas.png   -> loss curves + distribuição de residuos
"""

import numpy as np
import pandas as pd
import os, warnings
from pathlib import Path
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

import yfinance as yf
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────────────────────────────────────

TICKER     = "QSR"
START      = "2015-01-01"
END        = "2026-03-23"
LOOKBACK   = 60          # Janela de dias de entrada
FORECAST   = 252         # ~12 meses úteis
EPOCHS     = 120
BATCH      = 32
LR         = 0.001
PATIENCE   = 15          # Early stopping
SCRIPT_DIR  = Path(__file__).resolve().parent
ROOT_DIR    = SCRIPT_DIR.parent
OUTPUTS_DIR = ROOT_DIR / "outputs"
FIGURES_DIR = ROOT_DIR / "figures"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

CURRENT_PRICE = 73.75
DEVICE = torch.device("cpu")
torch.manual_seed(42)
np.random.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# 1. DOWNLOAD E FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("  LSTM QSR — Restaurant Brands International (PyTorch)")
print("=" * 60)
print(f"\n[1/5] Baixando {TICKER} via yfinance ({START} -> {END})...")

raw = yf.download(TICKER, start=START, end=END, auto_adjust=True, progress=False)

if raw.empty or len(raw) < 100:
    raise ValueError(f"Dados insuficientes para {TICKER}")

if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)

df = raw[["Close", "Volume"]].copy()
df.columns = ["close", "volume"]
df = df.dropna()

# Feature engineering
df["ma_20"]    = df["close"].rolling(20).mean()
df["ma_50"]    = df["close"].rolling(50).mean()
df["ma_200"]   = df["close"].rolling(200).mean()
df["vol_ma"]   = df["volume"].rolling(20).mean()
df["vol_ratio"] = df["volume"] / (df["vol_ma"] + 1e-9)

# RSI 14
delta = df["close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
df["rsi_14"] = 100 - 100 / (1 + gain / (loss + 1e-9))

# MACD
ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
df["macd"]   = ema12 - ema26
df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()

# Bollinger
std20 = df["close"].rolling(20).std()
df["bb_upper"] = df["ma_20"] + 2 * std20
df["bb_lower"] = df["ma_20"] - 2 * std20
df["bb_pct"]   = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-9)

# Log return e vol
df["log_ret"] = np.log(df["close"] / df["close"].shift(1))
df["vol_30d"] = df["log_ret"].rolling(30).std() * np.sqrt(252)

df = df.dropna()
print(f"       Registros apos features: {len(df):,} dias")

FEATURES = ["close","ma_20","ma_50","rsi_14","macd","signal",
            "bb_pct","vol_ratio","log_ret","vol_30d"]

# ─────────────────────────────────────────────────────────────────────────────
# 2. ESCALONAMENTO E SEQUÊNCIAS
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/5] Pre-processando...")

data = df[FEATURES].values.astype(np.float32)
scaler = MinMaxScaler(feature_range=(0, 1))
scaled = scaler.fit_transform(data).astype(np.float32)

X_list, y_list = [], []
for i in range(LOOKBACK, len(scaled)):
    X_list.append(scaled[i - LOOKBACK:i])
    y_list.append(scaled[i, 0])

X_arr = np.array(X_list, dtype=np.float32)
y_arr = np.array(y_list, dtype=np.float32).reshape(-1, 1)

split = int(len(X_arr) * 0.80)
X_train, X_test = X_arr[:split], X_arr[split:]
y_train, y_test = y_arr[:split], y_arr[split:]

print(f"       Treino: {len(X_train):,}  Teste: {len(X_test):,}  Features: {len(FEATURES)}")

# DataLoaders
train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
test_ds  = TensorDataset(torch.from_numpy(X_test), torch.from_numpy(y_test))
train_dl = DataLoader(train_ds, batch_size=BATCH, shuffle=False)
test_dl  = DataLoader(test_ds, batch_size=BATCH, shuffle=False)

# ─────────────────────────────────────────────────────────────────────────────
# 3. MODELO LSTM (PyTorch)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/5] Treinando LSTM (PyTorch)...")

class LSTMModel(nn.Module):
    def __init__(self, n_feat, hidden1=128, hidden2=64, hidden3=32, drop=0.2):
        super().__init__()
        self.lstm1 = nn.LSTM(n_feat, hidden1, batch_first=True)
        self.drop1 = nn.Dropout(drop)
        self.lstm2 = nn.LSTM(hidden1, hidden2, batch_first=True)
        self.drop2 = nn.Dropout(drop)
        self.lstm3 = nn.LSTM(hidden2, hidden3, batch_first=True)
        self.drop3 = nn.Dropout(0.15)
        self.fc1   = nn.Linear(hidden3, 32)
        self.relu  = nn.ReLU()
        self.fc2   = nn.Linear(32, 1)

    def forward(self, x):
        out, _ = self.lstm1(x)
        out = self.drop1(out)
        out, _ = self.lstm2(out)
        out = self.drop2(out)
        out, _ = self.lstm3(out)
        out = self.drop3(out[:, -1, :])   # último passo
        out = self.relu(self.fc1(out))
        return self.fc2(out)

model = LSTMModel(n_feat=len(FEATURES)).to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)
criterion = nn.HuberLoss()
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, factor=0.5, patience=7, min_lr=1e-6)

train_losses, val_losses = [], []
best_val = float("inf")
best_state = None
patience_counter = 0

for epoch in range(1, EPOCHS + 1):
    # Treino
    model.train()
    epoch_loss = 0.0
    for xb, yb in train_dl:
        xb, yb = xb.to(DEVICE), yb.to(DEVICE)
        optimizer.zero_grad()
        pred = model(xb)
        loss = criterion(pred, yb)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        epoch_loss += loss.item() * len(xb)
    epoch_loss /= len(train_ds)

    # Validação
    model.eval()
    val_loss = 0.0
    with torch.no_grad():
        for xb, yb in test_dl:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            pred = model(xb)
            val_loss += criterion(pred, yb).item() * len(xb)
    val_loss /= len(test_ds)

    train_losses.append(epoch_loss)
    val_losses.append(val_loss)
    scheduler.step(val_loss)

    if val_loss < best_val:
        best_val = val_loss
        best_state = {k: v.clone() for k, v in model.state_dict().items()}
        patience_counter = 0
    else:
        patience_counter += 1
        if patience_counter >= PATIENCE:
            print(f"       Early stopping em epoch {epoch}")
            break

    if epoch % 20 == 0 or epoch == 1:
        print(f"       Epoch {epoch:3d}  train={epoch_loss:.5f}  val={val_loss:.5f}")

model.load_state_dict(best_state)
epochs_run = len(train_losses)
print(f"       Melhor val loss: {best_val:.5f}  ({epochs_run} epochs)")

# ─────────────────────────────────────────────────────────────────────────────
# 4. AVALIAÇÃO
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/5] Avaliando no conjunto de teste...")

def inverse_close(arr_1d):
    """Inverte a normalização apenas para a coluna Close (índice 0)."""
    tmp = np.zeros((len(arr_1d), len(FEATURES)), dtype=np.float32)
    tmp[:, 0] = arr_1d
    return scaler.inverse_transform(tmp)[:, 0]

model.eval()
with torch.no_grad():
    X_t = torch.from_numpy(X_test).to(DEVICE)
    y_pred_s = model(X_t).cpu().numpy().flatten()

y_test_real = inverse_close(y_test.flatten())
y_pred_real = inverse_close(y_pred_s)

rmse = np.sqrt(mean_squared_error(y_test_real, y_pred_real))
mae  = mean_absolute_error(y_test_real, y_pred_real)
r2   = r2_score(y_test_real, y_pred_real)
mape = np.mean(np.abs((y_test_real - y_pred_real) / (y_test_real + 1e-9))) * 100

print(f"       RMSE : USD {rmse:.4f}")
print(f"       MAE  : USD {mae:.4f}")
print(f"       MAPE : {mape:.2f}%")
print(f"       R2   : {r2:.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# 5. PREVISÃO 12 MESES (ROLLING)
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n[5/5] Gerando previsao de {FORECAST} dias para frente...")

last_seq = scaled[-LOOKBACK:].copy()
forecast_prices = []

model.eval()
with torch.no_grad():
    for _ in range(FORECAST):
        inp = torch.from_numpy(last_seq[np.newaxis]).to(DEVICE)
        pred_s = model(inp).cpu().numpy()[0, 0]
        forecast_prices.append(pred_s)
        new_row = last_seq[-1].copy()
        new_row[0] = pred_s
        last_seq = np.vstack([last_seq[1:], new_row])

forecast_prices = inverse_close(np.array(forecast_prices, dtype=np.float32))

last_date    = df.index[-1]
future_dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=FORECAST)

price_6m  = forecast_prices[min(125, FORECAST-1)]
price_12m = forecast_prices[-1]
pct_12m   = (price_12m / CURRENT_PRICE - 1) * 100

print()
print("  RESUMO DA PREVISAO LSTM (QSR):")
print(f"  Preco atual (mercado)  : USD {CURRENT_PRICE:.2f}")
print(f"  Preco base (modelo)    : USD {df['close'].iloc[-1]:.2f}")
print(f"  Previsao +6 meses      : USD {price_6m:.2f}")
print(f"  Previsao +12 meses     : USD {price_12m:.2f}")
print(f"  Variacao esperada 12m  : {pct_12m:+.1f}%")
print(f"  RMSE (teste)           : USD {rmse:.2f}")
print(f"  R2 (teste)             : {r2:.4f}")

# Carregar percentis Monte Carlo se disponível
mc_csv = OUTPUTS_DIR / "monte_carlo_simulations.csv"
target_p50 = target_p10 = target_p90 = None
if mc_csv.exists():
    mc_df = pd.read_csv(mc_csv)
    target_p10 = mc_df["preco_simulado"].quantile(0.10)
    target_p50 = mc_df["preco_simulado"].quantile(0.50)
    target_p90 = mc_df["preco_simulado"].quantile(0.90)
    print(f"  Alvo Monte Carlo P50   : USD {target_p50:.2f}")

# ─────────────────────────────────────────────────────────────────────────────
# 6. GRÁFICO 1 — HISTÓRICO + PREVISÃO
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(15, 8))
fig.patch.set_facecolor("#FFFFFF")
ax.set_facecolor("#FFFFFF")

ax.plot(df.index, df["close"], color="#333333", lw=1.5,
        label="Preço Histórico QSR", alpha=0.9)

test_dates = df.index[split + LOOKBACK: split + LOOKBACK + len(y_test_real)]
ax.plot(test_dates, y_test_real, color="#27AE60", lw=1.2,
        alpha=0.6, label="Real (conjunto de teste)")
ax.plot(test_dates, y_pred_real, color="#E67E22", lw=1.2,
        alpha=0.8, ls="--", label="LSTM previsto (teste)")

ax.plot(future_dates, forecast_prices, color="#C30D1A", lw=2.2,
        ls="-", label=f"Previsão LSTM 12 meses", zorder=10)

sigma = np.linspace(rmse, rmse * 2.5, FORECAST)
ax.fill_between(future_dates,
                forecast_prices - sigma, forecast_prices + sigma,
                color="#C30D1A", alpha=0.15, label="Intervalo incerteza")

ax.axhline(CURRENT_PRICE, color="#000000", lw=1.5, ls=":",
           label=f"Preço Atual: USD {CURRENT_PRICE:.2f}", alpha=0.7)
ax.axvline(last_date, color="#666666", lw=1.2, ls="--", alpha=0.7)
ax.text(last_date, df["close"].min() + 2, " Hoje",
        color="#333333", fontsize=9, va="bottom")

if target_p50:
    ax.axhline(target_p50, color="#2980B9", lw=1.5, ls=":",
               label=f"Monte Carlo P50: USD {target_p50:.2f}", alpha=0.85)
    ax.fill_between([future_dates[0], future_dates[-1]],
                    target_p10, target_p90,
                    color="#2980B9", alpha=0.07,
                    label=f"Faixa MC P10-P90")

ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

ax.set_xlabel("Data", color="#333333", fontsize=11)
ax.set_ylabel("Preço (USD)", color="#333333", fontsize=11)
ax.set_title(
    f"LSTM PyTorch — Previsão de Preço  |  Restaurant Brands International (QSR)\n"
    f"RMSE: USD {rmse:.2f}  |  MAE: USD {mae:.2f}  |  MAPE: {mape:.1f}%  |  R2: {r2:.4f}",
    color="#8B0000", fontsize=13, fontweight="bold", pad=15
)
ax.tick_params(colors="#333333")
for sp in ax.spines.values():
    sp.set_color("#CCCCCC")
ax.legend(framealpha=0.9, labelcolor="#333333", fontsize=9, loc="upper left", ncol=2, facecolor="white", edgecolor="#CCCCCC")

box_txt = (
    f"Previsão 12m: USD {price_12m:.2f} ({pct_12m:+.1f}%)\n"
    f"Previsão 6m:  USD {price_6m:.2f}\n"
    f"RMSE: USD {rmse:.2f}  R2: {r2:.4f}\n"
    f"Epochs: {epochs_run}  |  Lookback: {LOOKBACK}d"
)
ax.text(0.99, 0.04, box_txt, transform=ax.transAxes,
        fontsize=9, color="#333333", va="bottom", ha="right",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#F8F9FA", edgecolor="#CCCCCC", alpha=0.9))

plt.tight_layout()
p1 = FIGURES_DIR / "lstm_pure_forecast.png"
plt.savefig(p1, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"\n  Grafico 1 salvo: {p1}")

# ─────────────────────────────────────────────────────────────────────────────
# 7. GRÁFICO 2 — LOSS CURVES + RESÍDUOS
# ─────────────────────────────────────────────────────────────────────────────
fig2, axes = plt.subplots(1, 2, figsize=(14, 6))
fig2.patch.set_facecolor("#FFFFFF")

ax_l = axes[0]
ax_l.set_facecolor("#FFFFFF")
ax_l.plot(train_losses, color="#95A5A6", lw=1.8, label="Treino Loss")
ax_l.plot(val_losses, color="#E67E22", lw=1.8, ls="-", label="Validação Loss")
ax_l.set_xlabel("Epoch", color="#333333")
ax_l.set_ylabel("Huber Loss", color="#333333")
ax_l.set_title("Curvas de Treinamento", color="#8B0000", fontweight="bold")
ax_l.tick_params(colors="#333333")
for sp in ax_l.spines.values():
    sp.set_color("#CCCCCC")
ax_l.legend(framealpha=0.9, labelcolor="#333333", facecolor="white", edgecolor="#CCCCCC")

residuals = y_test_real - y_pred_real
ax_r = axes[1]
ax_r.set_facecolor("#FFFFFF")
ax_r.hist(residuals, bins=40, color="#2C3E50", edgecolor="white", alpha=0.9)
ax_r.axvline(0, color="#000000", lw=1.5, ls="--")
ax_r.axvline(np.mean(residuals), color="#E67E22", lw=1.5, ls="-.",
             label=f"Média: {np.mean(residuals):.2f}")
ax_r.set_xlabel("Resíduo (USD)", color="#333333")
ax_r.set_ylabel("Frequência", color="#333333")
ax_r.set_title(f"Distribuição dos Resíduos\nRMSE={rmse:.2f}  MAE={mae:.2f}",
               color="#8B0000", fontweight="bold")
ax_r.tick_params(colors="#333333")
for sp in ax_r.spines.values():
    sp.set_color("#CCCCCC")
ax_r.legend(framealpha=0.9, labelcolor="#333333", facecolor="white", edgecolor="#CCCCCC")

plt.suptitle("LSTM QSR — Diagnóstico do Modelo (PyTorch)",
             color="#8B0000", fontsize=13, fontweight="bold", y=1.01)
plt.tight_layout()
p2 = FIGURES_DIR / "lstm_pure_diagnostics.png"
plt.savefig(p2, dpi=150, bbox_inches="tight", facecolor=fig2.get_facecolor())
plt.close()
print(f"  Grafico 2 salvo: {p2}")
print("\nLSTM concluido com sucesso!")
