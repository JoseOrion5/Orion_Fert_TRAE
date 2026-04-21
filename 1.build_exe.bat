
@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "OUTPUT_DIR=%SCRIPT_DIR%Fertilizante corrigida"
set "SRC_DIR=%SCRIPT_DIR%src"
if not exist "%SRC_DIR%" (
    set "SRC_DIR=%SCRIPT_DIR%.1src"
)
set "MAIN_FILE=%SRC_DIR%\main.py"
if not exist "%MAIN_FILE%" (
    set "MAIN_FILE=%SRC_DIR%\1.main.py"
)
set "WORK_DIR=%SRC_DIR%\build\OrionAgroquimSimulator"
set "SPEC_FILE=%SRC_DIR%\OrionAgroquimSimulator.spec"
if not exist "%SPEC_FILE%" (
    set "SPEC_FILE=%SRC_DIR%\1.OrionAgroquimSimulator.spec"
)
set "LEGACY_DIST_EXE=%SRC_DIR%\dist\OrionAgroquimSimulator.exe"
set "REQ_FILE=%SCRIPT_DIR%requirements.txt"
if not exist "%REQ_FILE%" (
    set "REQ_FILE=%SCRIPT_DIR%1.requirements.txt"
)

if not exist "%SRC_DIR%" (
    echo.
    echo ERRO: Pasta de codigo-fonte nao encontrada!
    echo Procurado em:
    echo - %SCRIPT_DIR%src
    echo - %SCRIPT_DIR%.1src
    echo.
    pause
    exit /b 1
)

if not exist "%MAIN_FILE%" (
    echo.
    echo ERRO: Arquivo principal nao encontrado!
    echo Procurado em:
    echo - %SRC_DIR%\main.py
    echo - %SRC_DIR%\1.main.py
    echo.
    pause
    exit /b 1
)

echo ==========================================
echo  Orion Agroquim Simulator - Build Script
echo  Iniciado em: %DATE% as %TIME%
echo ==========================================
echo.
echo Verificando Python...

set PYTHON_CMD=python
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%.venv\Scripts\python.exe"
    echo Python encontrado na virtualenv do projeto
    goto :found
)

python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Python encontrado (comando: python)
    goto :found
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Python encontrado (comando: py)
    set PYTHON_CMD=py
    goto :found
)

echo.
echo ERRO: Python nao encontrado!
echo.
echo Para resolver:
echo 1. Baixe o Python em: https://www.python.org/downloads/
echo 2. Durante a instalacao, MARQUE a opcao: "Add Python to PATH"
echo 3. Tente rodar este arquivo novamente.
echo.
pause
exit /b

:found
echo.
echo Instalando dependencias...
if not exist "%REQ_FILE%" (
    echo.
    echo ERRO: Arquivo requirements nao encontrado!
    echo Procurado em:
    echo - %SCRIPT_DIR%requirements.txt
    echo - %SCRIPT_DIR%1.requirements.txt
    echo.
    pause
    exit /b 1
)
"%PYTHON_CMD%" -m pip install -r "%REQ_FILE%"
if %errorlevel% neq 0 (
    echo.
    echo ERRO: Falha ao instalar dependencias.
    echo Verifique sua conexao e tente novamente.
    echo.
    pause
    exit /b 1
)

if not exist "%OUTPUT_DIR%" (
    mkdir "%OUTPUT_DIR%"
)

if exist "%WORK_DIR%" (
    rmdir /s /q "%WORK_DIR%"
)

if exist "%SPEC_FILE%" (
    del /q "%SPEC_FILE%"
)

if exist "%OUTPUT_DIR%\OrionAgroquimSimulator.exe" (
    del /q "%OUTPUT_DIR%\OrionAgroquimSimulator.exe"
)

if exist "%LEGACY_DIST_EXE%" (
    del /q "%LEGACY_DIST_EXE%"
)

echo.
echo Construindo o executavel...
pushd "%SRC_DIR%"
"%PYTHON_CMD%" -m PyInstaller --noconfirm --clean --onefile --windowed --name "OrionAgroquimSimulator" --hidden-import flet_desktop --collect-all flet_desktop --add-data "%SCRIPT_DIR%INSUMOS_IN39_2018.csv;." --add-data "%SCRIPT_DIR%ADITIVOS_IN39_2018.csv;." --distpath "%OUTPUT_DIR%" --workpath "%SRC_DIR%\build" "%MAIN_FILE%"
if %errorlevel% neq 0 (
    popd
    echo.
    echo ERRO: Falha ao construir o executavel (PyInstaller).
    echo.
    pause
    exit /b 1
)
popd

echo.
echo ==========================================
echo  CONCLUIDO!
echo  O executavel foi criado em: %OUTPUT_DIR%\OrionAgroquimSimulator.exe
echo ==========================================
pause
