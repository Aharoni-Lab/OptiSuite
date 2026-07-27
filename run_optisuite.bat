@echo off
set "ROOT=%~dp0"

start "2camera ZeroMQ" /D "%ROOT%Python versions\OCS_current_workspace_052825" cmd /k "venv\Scripts\python.exe 2camera_ZeroMQ_06132026.py"
start "SC3U Stage Control" /D "C:\Users\stimscope1\Documents\Stage_control\SC3U_stage_control\SC3U_stage_control\bin\Debug\" cmd /k "SC3U_stage_control.exe"
