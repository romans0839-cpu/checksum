@echo off
rem collect_indicators.bat - CHECK ONLY: fetch BLS indicators and print them. Nothing is saved on this PC. (ASCII only)
rem The real collection runs on the server (pipeline/console/jobs.py). Its result is on the console sheet, tab "today status".
cd /d C:\usstock-sub
python -m pipeline.collect.bls --dry-run
echo.
pause
