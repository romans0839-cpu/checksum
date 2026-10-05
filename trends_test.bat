@echo off
rem trends_test.bat - fetch trending searches (KR, US) and print them. Nothing is saved. (ASCII only)
cd /d C:\usstock-sub
python -m pipeline.collect.trends --dry-run
echo.
pause
