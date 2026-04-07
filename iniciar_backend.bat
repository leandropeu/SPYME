@echo off
cd /d %~dp0backend

if not exist .venv (
  py -3 -m venv .venv
)

call .venv\Scripts\activate
py -3 -m pip install -r requirements.txt
py -3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
