@echo off
cd /d "%~dp0"
title UserScope Dashboard
python app\server.py
pause