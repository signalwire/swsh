REM Verify pip and pyinstaller are available

for /f %%i in ('where pip') do set PIP=%%i
for /f %%i in ('where pyinstaller') do set PYINSTALLER=%%i

echo %PIP%
echo %PYINSTALLER%

REM Run setup.py
REM Installs all required modules for SWiSH
pip install .

REM Do patches

REM "c:\Program Files\Git\usr\bin\patch.exe" "c:\users\autum\documents\github\build env\buildenv\lib\site-packages\cmd2\cmd2.py" swsh\patches\cmd2.patch

for /f "tokens=2" %%a in ('pip show cmd2 ^| findstr "Location"') do set CMD_LOC=%%a
for /f "tokens=2" %%a in ('pip show pygments ^| findstr "Location"') do set PYGMENTS_LOC=%%a


"c:\Program Files\Git\usr\bin\patch.exe" %CMD_LOC%\cmd2\cmd2.py swsh\patches\cmd2.patch
"c:\Program Files\Git\usr\bin\patch.exe" %CMD_LOC%\cmd2\cmd2.py swsh\patches\do_history.patch
"c:\Program Files\Git\usr\bin\patch.exe" %PYGMENTS_LOC%\pygments\formatters\_mapping.py swsh\patches\pygment_mapping.patch

copy swsh\patches\swishcolor.py %PYGMENTS_LOC%\pygments\formatters

REM Run build
%PYINSTALLER% build-swsh.py --onefile -n swsh

timeout /t 60