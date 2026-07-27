@echo off
REM D3OA 测试启动器
REM 用装有 pygame-ce + pywin32 的解释器跑测试套件（L1 纯逻辑 + L2 渲染断路 + L3 窗口冒烟）
setlocal
set "PY=C:\Users\Cao Zuohua (Be)\AppData\Local\Python\bin\python.exe"
if not exist "%PY%" (
    echo [错误] 找不到 Python: %PY%
    pause
    exit /b 1
)
echo === L1+L2 逻辑与渲染测试 ===
"%PY%" "%~dp0tests\test_core.py"
echo.
echo === L3 窗口冒烟（需桌面会话，否则自动 SKIP）===
"%PY%" "%~dp0tests\test_overlay_smoke.py"
endlocal
