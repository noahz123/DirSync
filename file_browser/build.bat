@echo off
echo Installing required packages...
pip install pyinstaller
echo Creating executable...
pyinstaller --onefile --noconsole --name FileBrowser file_chooser.py
echo Build complete!
pause
