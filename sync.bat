@echo off
rem sync.bat - bring this folder up to date with the GitHub repository. The repository is the original (D24); this folder is a copy. (ASCII only)
cd /d C:\usstock-sub
git pull --ff-only
if errorlevel 1 echo [!] Pull failed - a file was edited in this folder. Tell Claude before doing anything else.
echo.
pause
