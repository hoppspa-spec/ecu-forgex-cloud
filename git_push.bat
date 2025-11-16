@echo off
echo ============================================
echo  Subiendo cambios a GitHub (ECU FORGE X)
echo ============================================
echo.

REM Activar entorno virtual (opcional, por si usas hooks)
call .venv\Scripts\activate

REM Añadir todos los cambios
git add .

REM Crear commit con fecha automática
set CURRENT_DATE=%date% %time%
git commit -m "Auto-commit: %CURRENT_DATE%"

REM Subir a GitHub
git push

echo.
echo Listo rey! Cambios subidos a GitHub exitosamente.
echo ============================================

pause
