@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   A股量化交易系统
echo ========================================
echo.
echo   正在启动...
echo   浏览器将自动打开 http://localhost:8501
echo.
echo   按 Ctrl+C 可以停止程序
echo ========================================
echo.

streamlit run app.py --server.headless true
pause
