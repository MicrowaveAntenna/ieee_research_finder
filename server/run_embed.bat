@echo off
setlocal
REM Encode index\corpus.jsonl with Qwen3-Embedding-0.6B on the GPU (Windows).
REM Nothing is installed; it uses the python of your own virtual environment.
REM Usage, from the unzipped a100-embed-job folder:
REM   run_embed.bat                                  (venv already activated)
REM   run_embed.bat D:\me\myenv\Scripts\python.exe   (no activation needed)
REM Optional: set BATCH=64 before running if the GPU is shared and memory is tight.

cd /d "%~dp0"
set "PY=%~1"
if "%PY%"=="" set "PY=python"
if not defined BATCH set "BATCH=128"
set "PYTHONIOENCODING=utf-8"

"%PY%" check_env.py
if errorlevel 1 exit /b 1

if not exist "models\Qwen3-Embedding-0.6B\model.safetensors" (
  echo.
  echo Model not found locally, downloading it now ...
  "%PY%" download_model.py
  if errorlevel 1 exit /b 1
)
set "HF_HUB_OFFLINE=1"

echo.
echo Encoding with batch size %BATCH% ...
"%PY%" scripts\build_index.py --no-bm25 --model Qwen/Qwen3-Embedding-0.6B --model-path models\Qwen3-Embedding-0.6B --device cuda --batch-size %BATCH%
if errorlevel 1 (
  echo.
  echo Encoding failed. If it says "out of memory", run:  set BATCH=32  then run this again.
  echo Progress is saved; a rerun continues where it stopped.
  exit /b 1
)

echo.
echo Done. Copy these two files back to the local Literature_finder_helper\index\ folder:
echo   %CD%\index\emb.npy
echo   %CD%\index\emb-meta.json
endlocal
