@echo off
cd /d %~dp0frontend
cmd /c npm install
cmd /c npm run dev -- --host 0.0.0.0 --port 5174
