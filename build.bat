@echo off
rem TeamsPet.exe 재빌드 스크립트
rem 핵심: 아나콘다 Library\bin을 PATH에 넣어야 PyInstaller가 의존 DLL을 찾는다
set PATH=C:\ProgramData\anaconda3\Library\bin;%PATH%
buildenv\Scripts\python -m PyInstaller --noconfirm --onefile --windowed --name TeamsPet --icon shiba.ico pet.py
echo.
echo Build done: dist\TeamsPet.exe
pause
