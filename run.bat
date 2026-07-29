@echo off
REM D3OA launcher - runs src/main.py with the pygame-ce + pywin32 interpreter.
REM NOTE: In Diablo 3, set video mode to Windowed (Fullscreen) or Windowed.
REM Uses 8.3 short path to avoid the parenthesis in "Cao Zuohua (Be)".
setlocal
set "PY=C:\Users\CAOZUO~1\AppData\Local\Python\bin\python.exe"
if not exist "%PY%" (
    echo ERROR: Python not found: %PY%
    echo Install pygame-ce and pywin32 for that interpreter.
    pause
    exit /b 1
)
"%PY%" "%~dp0src\main.py" %*
endlocal
pause
