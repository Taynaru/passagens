@echo off
REM Executa um ciclo de monitoramento. Use este .bat no Agendador de Tarefas do Windows.
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py run
