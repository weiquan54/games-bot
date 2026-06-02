@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动游戏自动点击工具...
python main.py
if %errorlevel% neq 0 (
    echo 启动失败，请确保已安装依赖：pip install -r requirements.txt
    pause
)
