@echo off
cd /d C:\Users\qingd\Documents\MarketListener
set PYTHONUNBUFFERED=1
desktop\.venv\Scripts\python.exe -m market_monitor serve --data-root data_control --host 0.0.0.0 --port 8765 --quiet >> data_control\f10\logs\sched_serve.log 2>&1
echo exit=%errorlevel% %date% %time% >> data_control\f10\logs\sched_serve.log
