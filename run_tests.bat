@echo off
REM D3OA test launcher - runs the test suite with the pygame-ce + pywin32 interpreter.
REM Uses 8.3 short path to avoid the parenthesis in "Cao Zuohua (Be)".
setlocal
set "PY=C:\Users\CAOZUO~1\AppData\Local\Python\bin\python.exe"
if not exist "%PY%" (
    echo ERROR: Python not found: %PY%
    echo Install pygame-ce and pywin32 for that interpreter.
    pause
    exit /b 1
)
"%PY%" tests/test_core.py
"%PY%" tests/test_render_pipeline.py
"%PY%" tests/test_api_auth.py
"%PY%" tests/test_thread_cleanup.py
"%PY%" tests/test_layout.py
"%PY%" tests/test_overlay_smoke.py
endlocal
pause
