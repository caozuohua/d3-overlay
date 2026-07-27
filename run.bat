@echo off
REM D3OA 启动器 —— 用同时装有 pygame-ce 与 pywin32 的解释器直接运行
REM 避免在本机多个 Python 间找解释器。游戏需无边框窗口化/窗口化模式运行。
setlocal
set "PY=C:\Users\Cao Zuohua (Be)\AppData\Local\Python\bin\python.exe"
if not exist "%PY%" (
    echo [错误] 找不到 Python: %PY%
    echo 请安装 pygame-ce 与 pywin32 到该解释器，或修改本文件里的 PY 路径。
    pause
    exit /b 1
)
"%PY%" "%~dp0src\main.py" %*
endlocal
