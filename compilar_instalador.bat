@echo off
chcp 65001 >nul
title Compilar Instalador - Sistema Legajo Digital DIRESA

echo.
echo ============================================================
echo     COMPILADOR DE INSTALADOR - LEGAJO DIGITAL DIRESA
echo ============================================================
echo.
echo Este script compilará el instalador .exe usando Inno Setup
echo.

REM Verificar si Inno Setup está instalado
set INNO_PATH="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set INNO_PATH_ALT="C:\Program Files\Inno Setup 6\ISCC.exe"

if exist %INNO_PATH% (
    set COMPILER=%INNO_PATH%
    goto :compile
)

if exist %INNO_PATH_ALT% (
    set COMPILER=%INNO_PATH_ALT%
    goto :compile
)

echo.
echo ERROR: Inno Setup no está instalado
echo.
echo Por favor, descarga e instala Inno Setup desde:
echo https://jrsoftware.org/isdl.php
echo.
echo Después de instalarlo, ejecuta este script nuevamente.
echo.
pause
exit /b 1

:compile
echo Inno Setup encontrado: %COMPILER%
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
    echo Creando archivo de licencia básico...
    echo MIT License > LICENSE.txt
)

REM Crear carpeta de salida si no existe
if not exist "instalador" (
    mkdir instalador
)

echo.
echo ============================================================
echo Compilando instalador...
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
    echo Revisa los mensajes de error anteriores.
    echo Verifica que todos los archivos necesarios estén presentes.
    echo.
)

echo.
pause
