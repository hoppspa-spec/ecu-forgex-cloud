@echo off
echo ============================================
echo   Iniciando ECU FORGE X (entorno local)
echo ============================================
echo.

REM Activar entorno virtual
call .venv\Scripts\activate

REM Ejecutar el servidor FastAPI
uvicorn app.main:app --reload

pause