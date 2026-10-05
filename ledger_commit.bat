@echo off
rem ledger_commit.bat - seal this week signal into the ledger, then verify (ASCII only)
cd /d C:\usstock-sub
python -m pipeline.ledger.commit
echo.
python -m pipeline.ledger.verify
echo.
pause
