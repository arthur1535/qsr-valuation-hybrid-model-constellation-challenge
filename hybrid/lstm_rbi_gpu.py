"""
Hybrid LSTM + valuation forecast for Restaurant Brands International (QSR).

The technical model learns short-term residual returns while the valuation
module anchors the 12-month path to DCF-consistent targets.
"""

from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
OUTPUTS_DIR = ROOT_DIR / "outputs"
FIGURES_DIR = ROOT_DIR / "figures"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
LOCK_PATH = OUTPUTS_DIR / "lstm_rbi_gpu.lock"
EXPECTED_PYTHON = Path(r"C:\gpu_venv\Scripts\python.exe")
POWERSHELL_EXE = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CURRENT_PID = os.getpid()
CURRENT_PARENT_PID = os.getppid()


def normalize_text(value: object) -> str:
    return str(value).replace("/", "\\").casefold().strip()


def run_powershell(script: str) -> subprocess.CompletedProcess[str]:
    command = [POWERSHELL_EXE, "-NoProfile", "-Command", script]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )


def query_python_processes() -> list[dict[str, object]]:
    ps_script = r"""
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $procs = Get-CimInstance Win32_Process |
      Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine } |
      Select-Object ProcessId, ExecutablePath, CommandLine
    $procs | ConvertTo-Json -Compress -Depth 2
    """
    result = run_powershell(ps_script)
    raw = result.stdout.strip()
    if result.returncode != 0 or not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def is_process_alive(pid: int) -> bool:
    result = run_powershell(f"@(Get-Process -Id {pid} -ErrorAction SilentlyContinue).Count")
    return result.stdout.strip() == "1"


def cleanup_stale_lock() -> None:
    if not LOCK_PATH.exists():
        return

    try:
        payload = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        LOCK_PATH.unlink(missing_ok=True)
        print(f"[LOCK] Removed corrupted lock: {LOCK_PATH}")
        return

    pid = int(payload.get("pid", -1))
    if pid <= 0 or not is_process_alive(pid):
        LOCK_PATH.unlink(missing_ok=True)
        print(f"[LOCK] Removed stale lock from PID {pid}: {LOCK_PATH}")


def cleanup_lock() -> None:
    if not LOCK_PATH.exists():
        return

    try:
        payload = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        LOCK_PATH.unlink(missing_ok=True)
        return

    if int(payload.get("pid", -1)) == CURRENT_PID:
        LOCK_PATH.unlink(missing_ok=True)


def write_lock() -> None:
    payload = {
        "pid": CURRENT_PID,
        "script": str(SCRIPT_PATH),
        "python": sys.executable,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    LOCK_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def find_other_script_instances() -> list[dict[str, object]]:
    script_marker = normalize_text(SCRIPT_PATH)
    others: list[dict[str, object]] = []
    for proc in query_python_processes():
        pid = int(proc.get("ProcessId", -1))
        cmdline = normalize_text(proc.get("CommandLine", ""))
        if pid <= 0 or pid in {CURRENT_PID, CURRENT_PARENT_PID}:
            continue
        if script_marker in cmdline:
            others.append(
                {
                    "pid": pid,
                    "command_line": proc.get("CommandLine", ""),
                    "python": proc.get("ExecutablePath", ""),
                }
            )
    return others


def terminate_process_tree(pid: int) -> None:
    result = subprocess.run(
        ["taskkill", "/PID", str(pid), "/F", "/T"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    if result.returncode != 0 and is_process_alive(pid):
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise RuntimeError(f"Failed to terminate PID {pid}. {detail}")

    deadline = time.time() + 10.0
    while time.time() < deadline:
        if not is_process_alive(pid):
            return
        time.sleep(0.25)

    raise RuntimeError(f"PID {pid} remained active after taskkill.")


def ensure_single_instance() -> None:
    cleanup_stale_lock()
    others = find_other_script_instances()
    if others:
        print("[LOCK] Previous runs detected. Closing them before starting...")
        for proc in others:
            print(f"[LOCK] Closing PID {proc['pid']} | {proc['python']}")
            terminate_process_tree(int(proc["pid"]))
        time.sleep(1.0)
        cleanup_stale_lock()

    write_lock()
    atexit.register(cleanup_lock)


def warn_if_unexpected_python() -> None:
    expected = EXPECTED_PYTHON.resolve(strict=False)
    current = Path(sys.executable).resolve(strict=False)
    if current == expected:
        return

    print(f"[WARN] Current Python : {current}")
    print(f"[WARN] Supported Python: {expected}")
    print(f"[WARN] Use: {expected} {SCRIPT_PATH}")


ensure_single_instance()

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yfinance as yf
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

from valuation.valuation_utils import build_anchor_curve, load_or_build_targets, load_valuation_premises


PREMISES = load_valuation_premises()
TARGETS = load_or_build_targets(PREMISES)

HYBRID_CFG = PREMISES["hybrid_model"]

TICKER = str(PREMISES["ticker"])
START = os.environ.get("LSTM_HISTORY_START", str(PREMISES["history_start"]))
END = os.environ.get(
    "LSTM_END",
    (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
)
LOOKBACK = int(os.environ.get("LSTM_LOOKBACK", HYBRID_CFG["lookback_default"]))
FORECAST = int(os.environ.get("LSTM_FORECAST_DAYS", TARGETS["forecast_days"]))
N_ENSEMBLE = int(os.environ.get("LSTM_N_ENSEMBLE", HYBRID_CFG["n_ensemble_default"]))
BATCH = int(os.environ.get("LSTM_BATCH", "64"))
LR = float(os.environ.get("LSTM_LR", "0.0005"))
PATIENCE = int(os.environ.get("LSTM_PATIENCE", HYBRID_CFG["patience_default"]))
MAX_EPOCHS = int(os.environ.get("LSTM_MAX_EPOCHS", HYBRID_CFG["max_epochs_default"]))
CURRENT_PRICE = float(TARGETS["current_price"])
PLOT_HISTORY_START = pd.Timestamp(PREMISES.get("plot_history_start", "2025-01-01"))

GPU_SAFE_MODE = True
DISABLE_CUDNN_RNN = True
SYNC_EACH_BATCH = False

FORCE_SYSTEM_CUDA_PATH = os.environ.get("LSTM_FORCE_SYSTEM_CUDA_PATH", "0") == "1"
CUDA_BIN = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2\bin"
CUDA_LIB = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2\lib\x64"
if FORCE_SYSTEM_CUDA_PATH:
    for cuda_path in (CUDA_BIN, CUDA_LIB):
        if os.path.isdir(cuda_path) and cuda_path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = cuda_path + ";" + os.environ.get("PATH", "")

BASE_TARGET = float(TARGETS["base_price"])
BEAR_TARGET = float(TARGETS["bear_price"])
BULL_TARGET = float(TARGETS["bull_price"])
BASE_DCF_PRICE = float(TARGETS["base_case_dcf_price"])
ANCHOR_DAILY_LOG_RETURN = (
    float(np.log(BASE_TARGET / CURRENT_PRICE) / FORECAST)
    if CURRENT_PRICE > 0 and BASE_TARGET > 0 and FORECAST > 0
    else 0.0
)


warn_if_unexpected_python()

if torch.cuda.is_available():
    DEVICE = torch.device("cuda:0")
    gpu_name = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"[GPU] {gpu_name}  |  VRAM: {vram:.1f} GB")
    torch.cuda.empty_cache()
    torch.set_num_threads(1)
    torch.backends.cudnn.benchmark = not GPU_SAFE_MODE
    torch.backends.cudnn.deterministic = GPU_SAFE_MODE
    if hasattr(torch.backends, "cuda") and hasattr(torch.backends.cuda, "matmul"):
        torch.backends.cuda.matmul.allow_tf32 = False
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.allow_tf32 = False
else:
    DEVICE = torch.device("cpu")
    print("[CPU] CUDA not available - running on CPU.")
    if EXPECTED_PYTHON.exists():
        print(f"[HINT] Run with: {EXPECTED_PYTHON} {SCRIPT_PATH}")

torch.manual_seed(42)
np.random.seed(42)

print("=" * 60)
print("  Hybrid LSTM + Valuation - Restaurant Brands International")
print(f"  Python: {sys.executable}")
print(f"  Device: {DEVICE}  |  Max epochs: {MAX_EPOCHS}  |  Patience: {PATIENCE}")
print(
    f"  Safe mode: {GPU_SAFE_MODE}  |  cuDNN RNN off: {DISABLE_CUDNN_RNN}  |  "
    f"sync each batch: {SYNC_EACH_BATCH}"
)
print(f"  Valuation source: {TARGETS['source']}  |  Base DCF: USD {BASE_DCF_PRICE:.2f}")
print(f"  Valuation bear/base/bull: USD {BEAR_TARGET:.2f} / USD {BASE_TARGET:.2f} / USD {BULL_TARGET:.2f}")
print("=" * 60)


def download_price_history(ticker: str, start: str, end: str) -> pd.DataFrame:
    last_error = "no details"
    for attempt in range(1, 4):
        try:
            raw_df = yf.download(
                ticker,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            if isinstance(raw_df.columns, pd.MultiIndex):
                raw_df.columns = raw_df.columns.get_level_values(0)
            if not raw_df.empty:
                return raw_df
            last_error = f"empty download on attempt {attempt}"
        except Exception as exc:  # pragma: no cover
            last_error = repr(exc)

        try:
            raw_df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
            if not raw_df.empty:
                return raw_df
            last_error = f"empty history on attempt {attempt}"
        except Exception as exc:  # pragma: no cover
            last_error = repr(exc)

        print(f"       [Retry {attempt}/3] download failed: {last_error}")
        time.sleep(float(attempt))
    raise RuntimeError(f"Failed to download history for {ticker}. Last error: {last_error}")


def build_feature_frame(close_series: pd.Series) -> pd.DataFrame:
    frame = pd.DataFrame({"close": close_series.astype(np.float64)})
    frame["ma_10"] = frame["close"].rolling(10).mean()
    frame["ma_20"] = frame["close"].rolling(20).mean()
    frame["ma_50"] = frame["close"].rolling(50).mean()
    frame["ma_200"] = frame["close"].rolling(200).mean()
    frame["ema_12"] = frame["close"].ewm(span=12, adjust=False).mean()
    frame["ema_26"] = frame["close"].ewm(span=26, adjust=False).mean()

    delta = frame["close"].diff()
    for window in (14, 28):
        gain = delta.clip(lower=0).rolling(window).mean()
        loss = (-delta.clip(upper=0)).rolling(window).mean()
        frame[f"rsi_{window}"] = 100.0 - 100.0 / (1.0 + gain / (loss + 1e-9))

    frame["macd"] = frame["ema_12"] - frame["ema_26"]
    frame["signal"] = frame["macd"].ewm(span=9, adjust=False).mean()
    frame["macd_hist"] = frame["macd"] - frame["signal"]

    for window, column in ((20, "bb20"), (50, "bb50")):
        moving_avg = frame["close"].rolling(window).mean()
        std = frame["close"].rolling(window).std()
        upper = moving_avg + 2.0 * std
        lower = moving_avg - 2.0 * std
        frame[f"{column}_pct"] = (frame["close"] - lower) / (upper - lower + 1e-9)

    frame["log_ret"] = np.log(frame["close"] / frame["close"].shift(1))
    frame["ret_5d"] = frame["close"].pct_change(5)
    frame["ret_20d"] = frame["close"].pct_change(20)
    frame["vol_10d"] = frame["log_ret"].rolling(10).std() * np.sqrt(252.0)
    frame["vol_30d"] = frame["log_ret"].rolling(30).std() * np.sqrt(252.0)
    frame["vol_60d"] = frame["log_ret"].rolling(60).std() * np.sqrt(252.0)
    frame["dist_ma50"] = (frame["close"] / frame["ma_50"] - 1.0).clip(-0.3, 0.3)
    frame["dist_ma200"] = (frame["close"] / frame["ma_200"] - 1.0).clip(-0.5, 0.5)
    return frame.dropna()


def build_decay_weights(steps: int) -> np.ndarray:
    if steps <= 0:
        return np.zeros(0, dtype=np.float64)
    if steps == 1:
        return np.zeros(1, dtype=np.float64)
    return np.linspace(1.0, 0.0, steps, dtype=np.float64)


def inverse_target_array(target_scaler: StandardScaler, values: np.ndarray) -> np.ndarray:
    return target_scaler.inverse_transform(np.asarray(values, dtype=np.float32).reshape(-1, 1)).reshape(-1)


def build_partition(
    scaled_features: np.ndarray,
    scaled_target: np.ndarray,
    current_close: np.ndarray,
    target_close: np.ndarray,
    target_dates: np.ndarray,
    start_idx: int,
    end_idx: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x_list = []
    y_list = []
    current_list = []
    next_list = []
    date_list = []
    first_target = max(start_idx, LOOKBACK - 1)
    for row_idx in range(first_target, end_idx):
        x_list.append(scaled_features[row_idx - LOOKBACK + 1 : row_idx + 1])
        y_list.append(float(scaled_target[row_idx]))
        current_list.append(float(current_close[row_idx]))
        next_list.append(float(target_close[row_idx]))
        date_list.append(target_dates[row_idx])
    return (
        np.asarray(x_list, dtype=np.float32),
        np.asarray(y_list, dtype=np.float32).reshape(-1, 1),
        np.asarray(current_list, dtype=np.float64),
        np.asarray(next_list, dtype=np.float64),
        np.asarray(date_list),
    )


print(f"\n[1/6] Downloading {TICKER} since {START}...")
raw = download_price_history(TICKER, START, END)
close_history = raw[["Close"]].copy().dropna()
close_history.columns = ["close"]
feature_df = build_feature_frame(close_history["close"])

FEATURES = [
    "close",
    "ma_10",
    "ma_20",
    "ma_50",
    "ema_12",
    "rsi_14",
    "rsi_28",
    "macd",
    "signal",
    "macd_hist",
    "bb20_pct",
    "bb50_pct",
    "log_ret",
    "ret_5d",
    "ret_20d",
    "vol_10d",
    "vol_30d",
    "vol_60d",
    "dist_ma50",
    "dist_ma200",
]
N_FEAT = len(FEATURES)
print(f"       Records after features: {len(feature_df):,} days  |  Features: {N_FEAT}")

feature_df["target_residual_ret"] = feature_df["log_ret"].shift(-1) - ANCHOR_DAILY_LOG_RETURN
feature_df["target_close"] = feature_df["close"].shift(-1)
feature_df["target_date"] = feature_df.index.to_series().shift(-1)
feature_df = feature_df.dropna(subset=["target_residual_ret", "target_close", "target_date"])

print("\n[2/6] Pre-processing and splitting...")
feature_values = feature_df[FEATURES].to_numpy(dtype=np.float32)
target_values = feature_df[["target_residual_ret"]].to_numpy(dtype=np.float32)
current_close_values = feature_df["close"].to_numpy(dtype=np.float64)
target_close_values = feature_df["target_close"].to_numpy(dtype=np.float64)
target_date_values = feature_df["target_date"].to_numpy()

total_rows = len(feature_df)
train_end = int(total_rows * 0.70)
val_end = int(total_rows * 0.85)

feature_scaler = StandardScaler()
target_scaler = StandardScaler()
feature_scaler.fit(feature_values[:train_end])
target_scaler.fit(target_values[:train_end])

scaled_features = feature_scaler.transform(feature_values).astype(np.float32)
scaled_target = target_scaler.transform(target_values).astype(np.float32).reshape(-1)

X_train, y_train, train_close, train_next_close, train_dates = build_partition(
    scaled_features, scaled_target, current_close_values, target_close_values, target_date_values, 0, train_end
)
X_val, y_val, val_close, val_next_close, val_dates = build_partition(
    scaled_features, scaled_target, current_close_values, target_close_values, target_date_values, train_end, val_end
)
X_test, y_test, test_close, test_next_close, test_dates = build_partition(
    scaled_features, scaled_target, current_close_values, target_close_values, target_date_values, val_end, total_rows
)

X_train_t = torch.from_numpy(X_train).to(DEVICE)
y_train_t = torch.from_numpy(y_train).to(DEVICE)
X_val_t = torch.from_numpy(X_val).to(DEVICE)
y_val_t = torch.from_numpy(y_val).to(DEVICE)
X_test_t = torch.from_numpy(X_test).to(DEVICE)
y_test_t = torch.from_numpy(y_test).to(DEVICE)

print(f"       Train/Val/Test sequences: {len(X_train):,} / {len(X_val):,} / {len(X_test):,}")
print(f"       Lookback: {LOOKBACK}d  |  Forecast horizon: {FORECAST} business days")
if DEVICE.type == "cuda":
    print(f"       VRAM reserved: {torch.cuda.memory_reserved(0) / 1024**3:.2f} GB")


class LSTMResidualNet(nn.Module):
    def __init__(self, n_feat: int, h1: int = 192, h2: int = 96, h3: int = 48, drop: float = 0.20):
        super().__init__()
        self.lstm1 = nn.LSTM(n_feat, h1, batch_first=True)
        self.norm1 = nn.LayerNorm(h1)
        self.drop1 = nn.Dropout(drop)
        self.lstm2 = nn.LSTM(h1, h2, batch_first=True)
        self.norm2 = nn.LayerNorm(h2)
        self.drop2 = nn.Dropout(drop)
        self.lstm3 = nn.LSTM(h2, h3, batch_first=True)
        self.norm3 = nn.LayerNorm(h3)
        self.drop3 = nn.Dropout(0.15)
        self.head = nn.Sequential(
            nn.Linear(h3, 32),
            nn.GELU(),
            nn.Dropout(0.10),
            nn.Linear(32, 16),
            nn.GELU(),
            nn.Linear(16, 1),
        )

    def _forward_impl(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm1(x)
        out = self.drop1(self.norm1(out))
        out, _ = self.lstm2(out)
        out = self.drop2(self.norm2(out))
        out, _ = self.lstm3(out)
        out = self.drop3(self.norm3(out[:, -1, :]))
        return self.head(out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.is_cuda and DISABLE_CUDNN_RNN:
            with torch.backends.cudnn.flags(enabled=False):
                return self._forward_impl(x)
        return self._forward_impl(x)


def count_params(model: nn.Module) -> int:
    return sum(param.numel() for param in model.parameters() if param.requires_grad)


def iter_batches(x_t: torch.Tensor, y_t: torch.Tensor, batch_size: int):
    for start_idx in range(0, x_t.size(0), batch_size):
        end_idx = start_idx + batch_size
        yield x_t[start_idx:end_idx], y_t[start_idx:end_idx]


def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(actual, predicted)))


def mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs((actual - predicted) / (actual + 1e-9))) * 100.0)


print(f"\n[3/6] Architecture: {count_params(LSTMResidualNet(n_feat=N_FEAT)):,} trainable parameters")


def train_one_model(seed: int):
    torch.manual_seed(seed)
    if DEVICE.type == "cuda":
        torch.cuda.empty_cache()

    model = LSTMResidualNet(n_feat=N_FEAT).to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        factor=0.5,
        patience=max(PATIENCE // 3, 4),
        min_lr=1e-6,
    )
    criterion = nn.HuberLoss(delta=0.8)

    best_val = float("inf")
    best_state = None
    patience_counter = 0
    train_losses = []
    val_losses = []
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        train_loss = 0.0
        for xb, yb in iter_batches(X_train_t, y_train_t, BATCH):
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(xb), yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            if DEVICE.type == "cuda" and SYNC_EACH_BATCH:
                torch.cuda.synchronize()
            train_loss += loss.item() * len(xb)
        train_loss /= len(X_train_t)

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for xb, yb in iter_batches(X_val_t, y_val_t, BATCH):
                val_loss += criterion(model(xb), yb).item() * len(xb)
        val_loss /= len(X_val_t)
        scheduler.step(val_loss)

        train_losses.append(train_loss)
        val_losses.append(val_loss)

        if epoch == 1 or epoch % 10 == 0:
            print(
                f"         [Seed {seed}] Epoch {epoch:4d}  "
                f"train={train_loss:.5f}  val={val_loss:.5f}"
            )

        if val_loss < best_val:
            best_val = val_loss
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"         [Seed {seed}] Early stop at epoch {epoch}  best val={best_val:.5f}")
                break

    if best_state is None:
        raise RuntimeError(f"Seed {seed} finished without a valid checkpoint.")

    model.load_state_dict(best_state)
    if DEVICE.type == "cuda":
        torch.cuda.empty_cache()
    return model, train_losses, val_losses, best_val


print(f"\n[4/6] Training ensemble of {N_ENSEMBLE} models...")
print(f"       Device: {DEVICE}  |  Batch: {BATCH}  |  Features: {N_FEAT}")

t_total_start = time.time()
ensemble_models = []
all_train_losses = []
all_val_losses = []

for ensemble_idx in range(N_ENSEMBLE):
    print(f"\n     [Ensemble {ensemble_idx + 1}/{N_ENSEMBLE}]")
    if DEVICE.type == "cuda":
        torch.cuda.synchronize()
        free_mem = (
            torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)
        ) / 1024**3
        print(f"       Free VRAM: {free_mem:.2f} GB")

    model, train_curve, val_curve, best_val = train_one_model(seed=42 + ensemble_idx)
    ensemble_models.append(model)
    all_train_losses.append(train_curve)
    all_val_losses.append(val_curve)
    print(f"       Best val loss: {best_val:.5f}  |  Epochs: {len(train_curve)}")

total_time = time.time() - t_total_start
if not ensemble_models:
    raise RuntimeError("No ensemble model finished training. Review timing or configuration.")

print(f"\n     Train total: {total_time / 60:.1f} min  |  {len(ensemble_models)} models")

print("\n[5/6] Evaluating technical model and building hybrid forecast...")
test_pred_stack = []
for model in ensemble_models:
    model.eval()
    with torch.no_grad():
        pred_scaled = model(X_test_t).cpu().numpy().reshape(-1)
    pred_residual = inverse_target_array(target_scaler, pred_scaled)
    pred_log_ret = ANCHOR_DAILY_LOG_RETURN + pred_residual
    pred_next_close = test_close * np.exp(pred_log_ret)
    test_pred_stack.append(pred_next_close)

test_pred_stack_arr = np.stack(test_pred_stack, axis=0)
tech_test_mean = test_pred_stack_arr.mean(axis=0)
tech_test_std = test_pred_stack_arr.std(axis=0)
test_actual = test_next_close
baseline_pred = test_close.copy()

rmse_test = rmse(test_actual, tech_test_mean)
mae_test = float(mean_absolute_error(test_actual, tech_test_mean))
mape_test = mape(test_actual, tech_test_mean)
r2_test = float(r2_score(test_actual, tech_test_mean))
rmse_baseline = rmse(test_actual, baseline_pred)
mae_baseline = float(mean_absolute_error(test_actual, baseline_pred))
mape_baseline = mape(test_actual, baseline_pred)
r2_baseline = float(r2_score(test_actual, baseline_pred))

print(f"       Technical RMSE : USD {rmse_test:.4f}")
print(f"       Technical MAE  : USD {mae_test:.4f}")
print(f"       Technical MAPE : {mape_test:.2f}%")
print(f"       Technical R2   : {r2_test:.4f}")
print(f"       Baseline RMSE  : USD {rmse_baseline:.4f}")
print(f"       Baseline MAE   : USD {mae_baseline:.4f}")
print(f"       Baseline MAPE  : {mape_baseline:.2f}%")
print(f"       Baseline R2    : {r2_baseline:.4f}")


def forecast_technical_path(model: nn.Module, close_values: list[float], steps: int) -> np.ndarray:
    history = list(float(value) for value in close_values)
    future_prices = []
    model.eval()

    with torch.no_grad():
        for _ in range(steps):
            feature_frame = build_feature_frame(pd.Series(history, dtype=np.float64))
            seq_raw = feature_frame[FEATURES].tail(LOOKBACK).to_numpy(dtype=np.float32)
            seq_scaled = feature_scaler.transform(seq_raw).astype(np.float32)
            inp = torch.from_numpy(seq_scaled[np.newaxis, ...]).to(DEVICE)
            pred_scaled = model(inp).cpu().numpy().reshape(-1)
            pred_residual = inverse_target_array(target_scaler, pred_scaled)[0]
            next_close = history[-1] * np.exp(ANCHOR_DAILY_LOG_RETURN + pred_residual)
            history.append(float(next_close))
            future_prices.append(float(next_close))

    return np.asarray(future_prices, dtype=np.float64)


last_date = close_history.index[-1]
forecast_history = close_history["close"].astype(np.float64).tolist()
forecast_history[-1] = CURRENT_PRICE

technical_future_stack = [forecast_technical_path(model, forecast_history, FORECAST) for model in ensemble_models]
technical_future_stack_arr = np.stack(technical_future_stack, axis=0)
technical_future_mean = technical_future_stack_arr.mean(axis=0)
future_dates = pd.bdate_range(start=last_date + pd.offsets.BDay(1), periods=FORECAST)

anchor_base = build_anchor_curve(CURRENT_PRICE, BASE_TARGET, FORECAST)
anchor_bear = build_anchor_curve(CURRENT_PRICE, BEAR_TARGET, FORECAST)
anchor_bull = build_anchor_curve(CURRENT_PRICE, BULL_TARGET, FORECAST)
decay_weights = build_decay_weights(FORECAST)

residual_log_stack = np.log(np.maximum(technical_future_stack_arr, 1e-6) / np.maximum(anchor_base, 1e-6))
hybrid_base_stack = anchor_base[np.newaxis, :] * np.exp(decay_weights[np.newaxis, :] * residual_log_stack)
hybrid_bear_stack = anchor_bear[np.newaxis, :] * np.exp(decay_weights[np.newaxis, :] * residual_log_stack)
hybrid_bull_stack = anchor_bull[np.newaxis, :] * np.exp(decay_weights[np.newaxis, :] * residual_log_stack)

hybrid_base_mean = hybrid_base_stack.mean(axis=0)
hybrid_base_std = hybrid_base_stack.std(axis=0)
hybrid_bear_mean = hybrid_bear_stack.mean(axis=0)
hybrid_bull_mean = hybrid_bull_stack.mean(axis=0)
hybrid_interval_lo = hybrid_base_mean - 1.96 * hybrid_base_std
hybrid_interval_hi = hybrid_base_mean + 1.96 * hybrid_base_std

hybrid_6m = hybrid_base_mean[min(125, FORECAST - 1)]
hybrid_12m = hybrid_base_mean[-1]
hybrid_12m_upside = (hybrid_12m / CURRENT_PRICE - 1.0) * 100.0

print()
print("  HYBRID FORECAST SUMMARY (QSR):")
print(f"  Current price            : USD {CURRENT_PRICE:.2f}")
print(f"  Last real close          : USD {close_history['close'].iloc[-1]:.2f}")
print(f"  Technical 12m            : USD {technical_future_mean[-1]:.2f}")
print(f"  Hybrid base +6m          : USD {hybrid_6m:.2f}")
print(f"  Hybrid base +12m         : USD {hybrid_12m:.2f}")
print(f"  Hybrid 95% CI 12m        : USD {hybrid_interval_lo[-1]:.2f} - USD {hybrid_interval_hi[-1]:.2f}")
print(f"  Hybrid bear/base/bull    : USD {hybrid_bear_mean[-1]:.2f} / USD {hybrid_base_mean[-1]:.2f} / USD {hybrid_bull_mean[-1]:.2f}")
print(f"  Expected 12m change      : {hybrid_12m_upside:+.1f}%")
print(f"  Ensemble size            : {len(ensemble_models)}")
print(f"  Total training time      : {total_time / 60:.1f} min")
if DEVICE.type == "cuda":
    print(f"  GPU used                 : {torch.cuda.get_device_name(0)}")

print("\n[6/6] Saving hybrid outputs and charts...")
df_out = pd.DataFrame(
    {
        "data": future_dates,
        "preco_tecnico": technical_future_mean,
        "preco_hibrido_base": hybrid_base_mean,
        "preco_hibrido_bear": hybrid_bear_mean,
        "preco_hibrido_bull": hybrid_bull_mean,
        "ancora_dcf_base": anchor_base,
        "ancora_dcf_bear": anchor_bear,
        "ancora_dcf_bull": anchor_bull,
        "intervalo_lo": hybrid_interval_lo,
        "intervalo_hi": hybrid_interval_hi,
        "previsao_media": hybrid_base_mean,
        "previsao_std": hybrid_base_std,
    }
)
csv_path = OUTPUTS_DIR / "hybrid_forecast.csv"
df_out.to_csv(csv_path, index=False)

plot_start = max(PLOT_HISTORY_START, pd.Timestamp(close_history.index.min()))
history_view = close_history.loc[close_history.index >= plot_start, "close"]
test_dates_ts = pd.to_datetime(test_dates)
test_mask = test_dates_ts >= plot_start

fig, ax = plt.subplots(figsize=(16, 9))
fig.patch.set_facecolor("#FFFFFF")
ax.set_facecolor("#FFFFFF")

ax.plot(history_view.index, history_view.values, color="#333333", lw=1.8, alpha=0.95, label="Real price history (from 2025)")
if np.any(test_mask):
    ax.plot(test_dates_ts[test_mask], test_actual[test_mask], color="#1F9D55", lw=1.5, alpha=0.85, label=f"Actual test price | RMSE={rmse_test:.2f}")
    ax.plot(
        test_dates_ts[test_mask],
        tech_test_mean[test_mask],
        color="#F4B41A",
        lw=1.4,
        ls="--",
        alpha=0.8,
        label=f"Technical predicted (test) | baseline RMSE={rmse_baseline:.2f}",
    )

ax.axvline(last_date, color="#777777", lw=1.2, ls="--", alpha=0.8)
ax.annotate("Forecast start", xy=(last_date, CURRENT_PRICE - 2.5), color="#333333", fontsize=9, ha="left")

ax.plot(future_dates, anchor_base, color="#F4B41A", lw=1.3, ls=":", alpha=0.9, label=f"DCF anchor base: USD {BASE_TARGET:.2f}")
ax.plot(future_dates, anchor_bear, color="#C8102E", lw=1.1, ls=":", alpha=0.55, label=f"DCF anchor bear: USD {BEAR_TARGET:.2f}")
ax.plot(future_dates, anchor_bull, color="#1F9D55", lw=1.1, ls=":", alpha=0.55, label=f"DCF anchor bull: USD {BULL_TARGET:.2f}")

ax.plot(future_dates, technical_future_mean, color="#7E57C2", lw=1.3, ls="--", alpha=0.75, label=f"Technical path 12m: USD {technical_future_mean[-1]:.2f}")
ax.plot(
    future_dates,
    hybrid_base_mean,
    color="#C30D1A",
    lw=2.6,
    zorder=10,
    label=f"Hybrid base 12m: USD {hybrid_12m:.2f} ({hybrid_12m_upside:+.1f}%)",
)
ax.plot(future_dates, hybrid_bear_mean, color="#A03A2A", lw=1.5, ls="-.", alpha=0.8, label="Hybrid bear")
ax.plot(future_dates, hybrid_bull_mean, color="#148F77", lw=1.5, ls="-.", alpha=0.8, label="Hybrid bull")
ax.fill_between(future_dates, hybrid_interval_lo, hybrid_interval_hi, color="#C30D1A", alpha=0.14, label="Hybrid 95% CI")
ax.axhline(CURRENT_PRICE, color="#000000", lw=1.5, ls=":", alpha=0.7, label=f"Current price: USD {CURRENT_PRICE:.2f}")

ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
ax.set_xlim(left=plot_start, right=future_dates[-1])
ax.set_xlabel("Date", color="#333333", fontsize=12)
ax.set_ylabel("Price (USD)", color="#333333", fontsize=12)
device_str = "RTX 4050 CUDA" if DEVICE.type == "cuda" else "CPU"
ax.set_title(
    f"Hybrid LSTM + DCF Anchor ({len(ensemble_models)} models, {total_time / 60:.0f}min train, {device_str})\n"
    f"QSR | technical RMSE USD {rmse_test:.2f} vs baseline USD {rmse_baseline:.2f} | real history shown from 2025",
    color="#8B0000",
    fontsize=13,
    fontweight="bold",
    pad=15,
)
ax.tick_params(colors="#333333")
for spine in ax.spines.values():
    spine.set_color("#CCCCCC")
ax.legend(framealpha=0.92, labelcolor="#333333", fontsize=8, loc="upper left", ncol=2, facecolor="#FFFFFF", edgecolor="#CCCCCC")

summary_box = (
    f"Valuation source: {TARGETS['source']}\n"
    f"Base DCF: USD {BASE_DCF_PRICE:.2f}\n"
    f"Hybrid 12m: USD {hybrid_12m:.2f}\n"
    f"Bear/Base/Bull: {hybrid_bear_mean[-1]:.1f} / {hybrid_base_mean[-1]:.1f} / {hybrid_bull_mean[-1]:.1f}\n"
    f"Technical RMSE: {rmse_test:.2f}\n"
    f"Real history window starts: {plot_start.date()}"
)
ax.text(
    0.995,
    0.02,
    summary_box,
    transform=ax.transAxes,
    fontsize=9,
    color="#333333",
    va="bottom",
    ha="right",
    bbox=dict(boxstyle="round,pad=0.5", facecolor="#FFFFFF", edgecolor="#CCCCCC", alpha=0.92),
)

plt.tight_layout()
forecast_path = FIGURES_DIR / "hybrid_path_forecast.png"
plt.savefig(forecast_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()

fig2, axes = plt.subplots(1, 2, figsize=(14, 6))
fig2.patch.set_facecolor("#FFFFFF")

ax_loss = axes[0]
ax_loss.set_facecolor("#FFFFFF")
loss_colors = ["#C8102E", "#F4B41A", "#4A4A4A", "#E04C5A", "#148F77"]
for idx, (train_curve, val_curve) in enumerate(zip(all_train_losses, all_val_losses)):
    color = loss_colors[idx % len(loss_colors)]
    ax_loss.plot(train_curve, color=color, lw=1.5, alpha=0.85, label=f"Train {idx + 1}")
    ax_loss.plot(val_curve, color=color, lw=1.5, alpha=0.45, ls="--")
ax_loss.set_xlabel("Epoch", color="#333333", fontsize=11)
ax_loss.set_ylabel("Huber loss", color="#333333", fontsize=11)
ax_loss.set_title(
    f"Residual-return loss per epoch - {len(ensemble_models)} models\n(solid=train, dashed=val)",
    color="#8B0000",
    fontweight="bold",
)
ax_loss.tick_params(colors="#333333")
for spine in ax_loss.spines.values():
    spine.set_color("#CCCCCC")
ax_loss.legend(framealpha=0.92, labelcolor="#333333", fontsize=8, facecolor="#FFFFFF", edgecolor="#CCCCCC")

ax_scatter = axes[1]
ax_scatter.set_facecolor("#FFFFFF")
scatter_err = np.abs(test_actual - tech_test_mean)
scatter = ax_scatter.scatter(test_actual, tech_test_mean, c=scatter_err, cmap="Reds", s=10, alpha=0.65)
plt.colorbar(scatter, ax=ax_scatter, label="Abs error (USD)").ax.yaxis.label.set_color("#333333")
low_bound = min(test_actual.min(), tech_test_mean.min(), baseline_pred.min()) - 1.5
high_bound = max(test_actual.max(), tech_test_mean.max(), baseline_pred.max()) + 1.5
ax_scatter.plot([low_bound, high_bound], [low_bound, high_bound], "--", color="#333333", lw=1.5, alpha=0.6, label="Perfect")
ax_scatter.set_xlabel("Actual next close (USD)", color="#333333", fontsize=11)
ax_scatter.set_ylabel("Technical predicted next close (USD)", color="#333333", fontsize=11)
ax_scatter.set_title(
    f"Technical model vs actual - Test set\nRMSE={rmse_test:.2f}  MAPE={mape_test:.1f}%  R2={r2_test:.4f}",
    color="#8B0000",
    fontweight="bold",
)
ax_scatter.tick_params(colors="#333333")
for spine in ax_scatter.spines.values():
    spine.set_color("#CCCCCC")
ax_scatter.legend(framealpha=0.92, labelcolor="#333333", facecolor="#FFFFFF", edgecolor="#CCCCCC")

diag_box = (
    f"Baseline RMSE: {rmse_baseline:.2f}\n"
    f"Baseline MAPE: {mape_baseline:.1f}%\n"
    f"Base target: USD {BASE_TARGET:.2f}\n"
    f"Current price: USD {CURRENT_PRICE:.2f}"
)
ax_scatter.text(
    0.98,
    0.02,
    diag_box,
    transform=ax_scatter.transAxes,
    fontsize=9,
    color="#333333",
    va="bottom",
    ha="right",
    bbox=dict(boxstyle="round,pad=0.4", facecolor="#FFFFFF", edgecolor="#CCCCCC", alpha=0.92),
)

plt.suptitle("Hybrid LSTM diagnostics | Technical component benchmarked against real prices", color="#8B0000", fontsize=13, fontweight="bold", y=1.01)
plt.tight_layout()
diag_path = FIGURES_DIR / "hybrid_diagnostics.png"
plt.savefig(diag_path, dpi=150, bbox_inches="tight", facecolor=fig2.get_facecolor())
plt.close()

print(f"  Forecast chart saved: {forecast_path}")
print(f"  Diagnostics chart saved: {diag_path}")
print(f"  Hybrid CSV saved: {csv_path}")
print("\nHybrid LSTM forecast completed successfully.")
