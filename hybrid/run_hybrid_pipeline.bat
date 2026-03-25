@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
set "VENV_PY=C:\gpu_venv\Scripts\python.exe"
set "MC_SCRIPT=%ROOT_DIR%\monte_carlo\montecarlo_rbi.py"
set "LSTM_SCRIPT=%SCRIPT_DIR%lstm_rbi_gpu.py"
set "POST_SCRIPT=%SCRIPT_DIR%post_process_lstm.py"
set "PYTHONUNBUFFERED=1"

echo ============================================================
echo   RTX 4050 CUDA Launcher - QSR Hybrid Pipeline
echo ============================================================
echo   Python    : %VENV_PY%
echo   MonteCarlo: %MC_SCRIPT%
echo   LSTM      : %LSTM_SCRIPT%
echo   Post      : %POST_SCRIPT%
echo ============================================================

if not exist "%VENV_PY%" (
    echo [ERROR] Ambiente GPU nao encontrado em "%VENV_PY%".
    echo [HINT] Create or update the GPU environment first.
    pause
    exit /b 1
)

pushd "%ROOT_DIR%"

echo [CHECK] Validando interpretador e GPU...
"%VENV_PY%" -c "import sys, torch; print('[CHECK] python:', sys.executable); print('[CHECK] torch:', torch.__version__); print('[CHECK] torch.cuda:', torch.version.cuda); print('[CHECK] CUDA:', torch.cuda.is_available()); print('[CHECK] GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
if errorlevel 1 (
    popd
    echo [ERROR] Falha no preflight da env GPU.
    pause
    exit /b 1
)

echo.
echo [1/3] Rodando valuation / Monte Carlo...
echo.
"%VENV_PY%" -u "%MC_SCRIPT%"
if errorlevel 1 (
    set "EXIT_CODE=%ERRORLEVEL%"
    popd
    echo [ERROR] Falha na etapa Monte Carlo.
    echo Execucao encerrada com codigo %EXIT_CODE%.
    pause
    exit /b %EXIT_CODE%
)

echo.
echo [2/3] Rodando LSTM hibrido...
echo.
"%VENV_PY%" -u "%LSTM_SCRIPT%"
if errorlevel 1 (
    set "EXIT_CODE=%ERRORLEVEL%"
    popd
    echo [ERROR] Falha na etapa LSTM hibrido.
    echo Execucao encerrada com codigo %EXIT_CODE%.
    pause
    exit /b %EXIT_CODE%
)

echo.
echo [3/3] Gerando grafico de sensibilidade final...
echo.
"%VENV_PY%" -u "%POST_SCRIPT%"
set "EXIT_CODE=%ERRORLEVEL%"

popd
echo.
if "%EXIT_CODE%"=="0" (
    echo Pipeline concluido com sucesso.
    echo Artefatos principais:
    echo   - outputs\monte_carlo_simulations.csv
    echo   - data\processed\valuation_targets.json
    echo   - outputs\hybrid_forecast.csv
    echo   - figures\hybrid_path_forecast.png
    echo   - figures\hybrid_diagnostics.png
    echo   - figures\hybrid_scenario_sensitivity.png
) else (
    echo [ERROR] Falha na etapa de sensibilidade final.
)
echo Execucao encerrada com codigo %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
