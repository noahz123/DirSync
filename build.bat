@echo off
echo Installing required packages...
pip install pyinstaller
echo Creating executable...
pyinstaller --onefile --noconsole --name DirSync DirSync.py
echo Build complete!
pause
