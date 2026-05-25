@echo off
chcp 65001 >nul
echo ========================================
echo   A股量化交易系统 - 首次安装
echo ========================================
echo.

echo [1/3] 安装依赖...
pip install -r requirements.txt -q
echo 完成.
echo.

echo [2/3] 初始化数据库...
python data/models.py
echo 完成.
echo.

echo [3/3] 获取示例数据（平安银行 000001）...
python data/fetch_daily.py --symbols 000001 --start 20240101 --end 20251231
echo.

echo ========================================
echo   安装完成！
echo.
echo   接下来试试回测：
echo   python backtest_main.py --strategy ma_crossover --symbols 000001 --start 2024-01-01 --end 2024-12-31
echo ========================================
pause
