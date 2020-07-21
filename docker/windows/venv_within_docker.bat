@echo off
REM server/docker/windows/bash_within_camcops_docker.bat
REM
REM Launches the "bash" command within one of the Docker containers running the
REM CRATE image.

setlocal

set THIS_DIR=%~dp0
set WITHIN_DOCKER=%THIS_DIR%\within_docker.bat

REM https://serverfault.com/questions/368054/run-an-interactive-bash-subshell-with-initial-commands-without-returning-to-the
REM https://stackoverflow.com/questions/59814742/docker-run-bash-init-file
"%WITHIN_DOCKER%" /bin/bash -c "source /crate/venv/bin/activate; exec /bin/bash"
