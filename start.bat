@echo off
title TerraLegalAI - Start Services
cd /d D:\TerraLegalAI

echo ========================================
echo  TerraLegalAI - Khoi dong dich vu
echo ========================================
echo.

echo [1/2] Kiem tra Docker...
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo  CANH BAO: Docker chua san sang. Hay mo Docker Desktop truoc!
    echo  Go phim bat ky de thoat...
    pause >nul
    exit /b 1
)

echo  Docker OK!
echo.
echo [2/2] Khoi dong tat ca services (PostgreSQL, Qdrant, Redis, Backend, Frontend)...
docker-compose up -d

echo.
if %errorlevel% equ 0 (
    echo  TAT CA SERVICES DA CHAY!
    echo.
    echo  Frontend : http://localhost:3000
    echo  Backend  : http://localhost:8000
    echo  API Docs : http://localhost:8000/docs
    echo.
    echo  Doi khoang 30-60 giay de backend khoi dong xong...
) else (
    echo  Co loi xay ra. Xem log: docker-compose logs
)

echo.
pause
