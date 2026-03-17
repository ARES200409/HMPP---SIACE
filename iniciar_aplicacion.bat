@echo off
chcp 65001 >nul
title Servidor - Sistema Escalafon HMPP

echo.
echo ============================================================
echo      SISTEMA DE ESCALAFON DIGITAL HMPP (MODO SEGURO)
echo ============================================================
echo.

REM --- PASO 0: Asegurar el directorio de trabajo ---
cd /d "%~dp0"

REM --- PASO 1: Buscar Python de forma inteligente ---
set "PY_CMD="

REM Prioridad 1: Buscar en la ruta donde se que esta instalado por tus capturas
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe""
)

REM Prioridad 2: Si no, intentar con comandos globales
if not defined PY_CMD (
    python --version >nul 2>&1 && set "PY_CMD=python"
)
if not defined PY_CMD (
    py --version >nul 2>&1 && set "PY_CMD=py"
)

if not defined PY_CMD (
    echo [ERROR] No se pudo encontrar Python 3.11 en ninguna ruta.
    echo Por favor, asegúrese de que Python esté instalado correctamente.
    pause
    exit /b 1
)

echo [OK] Motor detectado: %PY_CMD%

REM --- PASO 2: Forzar configuración de seguridad ---
echo [INFO] Sincronizando variables de entorno...

REM Fallback de seguridad por si el .env falla
set "SECRET_KEY=legajo_20260304101114_hmpp_secret_key_2026"

REM Intentar copiar el .env si no existe en la carpeta actual
if not exist ".env" (
    if exist "%LOCALAPPDATA%\LegajoDigitalHMPP\.env" (
        copy /Y "%LOCALAPPDATA%\LegajoDigitalHMPP\.env" ".env" >nul 2>&1
    )
)

REM --- PASO 3: Asegurar motor de servidor ---
echo [INFO] Verificando motor Waitress...
%PY_CMD% -m pip install waitress >nul 2>&1

echo.
echo ============================================================
echo   SISTEMA LISTO: Mantén esta ventana abierta.
echo ============================================================
echo.
echo Abrir en el navegador: http://localhost:5001
echo.

REM --- PASO 4: Lanzar el servidor con Waitress ---
%PY_CMD% -m waitress --host=0.0.0.0 --port=5001 wsgi:app

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] El servidor no pudo iniciar.
    echo Posible causa: Conflicto de permisos o Python desconfigurado.
    echo.
    echo SOLUCION: Haga CLIC DERECHO en el icono del escritorio
    echo           y elija "EJECUTAR COMO ADMINISTRADOR".
    echo.
    pause
)