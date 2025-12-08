@echo off
chcp 65001 >nul
REM -----------------------------------------------------------------
REM --- LANZADOR DE LA APLICACIÓN DE LEGAJO DIGITAL ---
REM -----------------------------------------------------------------
title Sistema de Legajo Digital DIRESA

echo.
echo ============================================================
echo     SISTEMA DE LEGAJO DIGITAL DIRESA
echo ============================================================
echo.
echo Iniciando el servidor de la aplicación...
echo.

REM Obtiene la ruta del directorio donde se encuentra este script
set "CURRENT_DIR=%~dp0"

REM Navega al directorio del script
cd /d "%CURRENT_DIR%"

REM Verificar si existe entorno virtual
if exist ".\venv\Scripts\waitress-serve.exe" (
    echo [INFO] Usando entorno virtual...
    set "WAITRESS_CMD=.\venv\Scripts\waitress-serve.exe"
) else (
    echo [INFO] Usando Python global...
    set "WAITRESS_CMD=waitress-serve"
)

REM Verificar si waitress está instalado
where waitress-serve >nul 2>&1
if %errorlevel% neq 0 (
    if not exist ".\venv\Scripts\waitress-serve.exe" (
        echo.
        echo [ERROR] Waitress no está instalado.
        echo.
        echo Por favor, instala las dependencias:
        echo    pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
)

REM Iniciar el servidor
echo.
echo Iniciando servidor en http://localhost:5001
echo.
echo IMPORTANTE: Mantén esta ventana abierta mientras uses la aplicación.
echo            Para detener el servidor, cierra esta ventana.
echo.

REM Iniciar waitress
%WAITRESS_CMD% --host=0.0.0.0 --port=5001 wsgi:app

REM Si el servidor se detiene, mostrar mensaje
echo.
echo El servidor se ha detenido.
pause
