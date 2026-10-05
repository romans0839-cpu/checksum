@echo off
rem collect_indicators.bat - fetch BLS indicators into the content DB (ASCII only)
cd /d C:\usstock-sub
python -m pipeline.collect.bls
echo.
pause
