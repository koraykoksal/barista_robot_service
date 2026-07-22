@REM @echo off
@REM cd /d "%~dp0"
@REM py -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
@REM pause



@echo off
set PORT=8000

cd /d "%~dp0"

echo Port %PORT% kullanan process kontrol ediliyor...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PORT% ^| findstr LISTENING') do (
    echo PID bulundu: %%a - sonlandiriliyor...
    taskkill /PID %%a /F
)

echo Coffe Machine Service running...
py -m uvicorn app:app --host 0.0.0.0 --port %PORT% --reload

pause
