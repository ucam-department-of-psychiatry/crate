@echo off
REM server/docker/windows/stop_camcops_docker.bat
REM
REM Takes down the Docker Compose application.

setlocal

set THIS_DIR=%~dp0
set DOCKER_COMPOSE_DIR=%THIS_DIR%\..\dockerfiles

REM We must change directory to pick up ".env" etc.

cd "%DOCKER_COMPOSE_DIR%"

REM Having done so, the default Docker Compose filenames include
REM docker-compose.yaml, so we don't need to specify that.

docker-compose down
