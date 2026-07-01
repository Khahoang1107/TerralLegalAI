@echo off
cd /d D:\TerraLegalAI
D:\TerraLegalAI\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > D:\TerraLegalAI\backend\dev.out.log 2> D:\TerraLegalAI\backend\dev.err.log
