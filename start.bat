@echo off
chcp 65001 > nul
title Group Facebook Bot - Dashboard
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py gui.py
) else (
    python gui.py
)
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] An error occurred while running the bot.
    pause
)
