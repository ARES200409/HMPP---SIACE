@echo off
chcp 65001 >nul
title Compilar Instalador - Sistema Digital HMPP

echo.
echo ============================================================
echo     COMPILADOR DE INSTALADOR - SISTEMA DIGITAL HMPP
echo ============================================================
echo.
echo Este script compilara el instalador .exe usando Inno Setup
echo.

REM Buscar Inno Setup en TODAS las rutas posibles (incluyendo AppData)
set INNO_PATH="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set INNO_PATH_ALT="C:\Program Files\Inno Setup 6\ISCC.exe"
set INNO_PATH_USER="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if exist %INNO_PATH% (
    set COMPILER=%INNO_PATH%
    goto :compile
)

if exist %INNO_PATH_ALT% (
    set COMPILER=%INNO_PATH_ALT%
    goto :compile
)

if exist %INNO_PATH_USER% (
    set COMPILER=%INNO_PATH_USER%
    goto :compile
)

echo.
echo ERROR: Inno Setup no esta instalado o no se encuentra.
echo.
echo Por favor, descarga e instala Inno Setup desde:
echo https://jrsoftware.org/isdl.php
echo.
echo Despues de instalarlo, ejecuta este script nuevamente.
echo.
pause
exit /b 1

:compile
echo Inno Setup encontrado exitosamente en: %COMPILER%
echo.
echo Verificando archivos necesarios...

REM Verificar que existe setup.iss
if not exist "setup.iss" (
    echo ERROR: No se encuentra el archivo setup.iss
    pause
    exit /b 1
)

REM Verificar que existe LICENSE.txt
if not exist "LICENSE.txt" (
    echo ADVERTENCIA: No se encuentra LICENSE.txt
    echo Creando archivo de licencia basico...
    echo MIT License > LICENSE.txt
)

REM Crear carpeta de salida si no existe
if not exist "instalador" (
    mkdir instalador
)

echo.
echo ============================================================
echo Compilando instalador de HMPP...
echo ============================================================
echo.

REM Compilar el instalador
%COMPILER% setup.iss

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo ¡INSTALADOR CREADO EXITOSAMENTE!
    echo ============================================================
    echo.
    echo El instalador se encuentra en:
    echo %CD%\instalador\
    echo.
    
    REM Listar archivos creados
    dir /B instalador\*.exe
    
    echo.
    echo Puedes distribuir este archivo .exe a los usuarios finales.
    echo.
    
    REM Preguntar si desea abrir la carpeta
    set /p ABRIR="¿Desea abrir la carpeta del instalador? (S/N): "
    if /i "%ABRIR%"=="S" (
        explorer instalador
    )
) else (
    echo.
    echo ============================================================
    echo ERROR AL COMPILAR EL INSTALADOR
    echo ============================================================
    echo.
    echo Revisa los mensajes de error anteriores en letras rojas.
    echo Verifica que todos los archivos necesarios esten presentes.
    echo.
)

echo.
pause