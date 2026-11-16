@echo off
rem Lanzador de cine en Windows: bin\windows-x64\cine.exe o la compilación local de motor\.
set "d=%~dp0"
if exist "%d%windows-x64\cine.exe" ( "%d%windows-x64\cine.exe" %* & exit /b %errorlevel% )
if exist "%d%..\motor\target\release\cine.exe" ( "%d%..\motor\target\release\cine.exe" %* & exit /b %errorlevel% )
echo cine: no hay binario para windows-x64 en %d%. Compilalo con: cargo build --release --manifest-path "%d%..\motor\Cargo.toml" 1>&2
exit /b 127
