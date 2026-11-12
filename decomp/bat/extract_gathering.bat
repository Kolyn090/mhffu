@echo off
setlocal
set "out=%~dp0..\output\en"
if not exist "%out%\" mkdir "%out%"
set "target=%out%\gathering.json"
set /a run=1
:choose_output
if not exist "%target%" goto run_extractor
set /a run+=1
set "target=%out%\gathering-%run%.json"
goto choose_output
:run_extractor
echo Writing "%target%"
py -B "%~dp0..\scripts\extract_gathering.py" "E:\Games\MH2G Game\En_DATA\DATA.BIN" "%target%"
exit /b %errorlevel%
