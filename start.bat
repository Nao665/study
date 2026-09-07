@echo off
chcp 65001 > nul
echo ===================================================
echo   韓国語単語抽出ウェブアプリを起動しています...
echo ===================================================

if not exist ".venv\Scripts\python.exe" (
    echo [エラー] 仮想環境が見つかりません。
    pause
    exit /b 1
)

.venv\Scripts\python.exe run.py
pause
