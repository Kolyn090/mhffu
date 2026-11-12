@echo off
setlocal
set "out=%~dp0..\output\en"
if not exist "%out%\" mkdir "%out%"
set "target=%out%\table-of-contents.csv"
set /a run=1
:choose_output
if not exist "%target%" goto run_extractor
set /a run+=1
set "target=%out%\table-of-contents-%run%.csv"
goto choose_output
:run_extractor
echo Writing "%target%"
py -B "%~dp0..\scripts\decode_mhfu.py" "E:\Games\MH2G Game\En_DATA\DATA.BIN" index "%target%"
exit /b %errorlevel%
