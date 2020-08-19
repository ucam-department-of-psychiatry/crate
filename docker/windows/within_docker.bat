@echo off
REM docker/windows/within_docker.bat
REM
REM Starts a container with the CRATE image and runs a command in it.

setlocal

set THIS_DIR=%~dp0
set DOCKER_COMPOSE_DIR=%THIS_DIR%\..\dockerfiles
set SERVICE=crate_workers

REM Don't echo things to stdout. People may want to redirect the output.
REM On the other hand, docker-compose splurges stuff to stderr and you can't stop
REM it, so we may as well too.

echo Executing command within the '%SERVICE%' Docker Compose service... 1>&2

REM We must change directory to pick up ".env" etc.

cd "%DOCKER_COMPOSE_DIR%"

REM Having done so, the default Docker Compose filenames include
REM docker-compose.yaml, so we don't need to specify that.

docker-compose run --rm "%SERVICE%" %*
REM                ^    ^^^^^^^^^^^ ^
REM                |    |           |
REM                |    |           +-- command
REM                |    +-- service (container)
REM                +-- remove container after run
REM
REM We could use any service with the same image; all should have equivalent
REM volumes mounted and the same environment. The "crate_celery" service is
REM started first (with the fewest dependencies) so will be fastest.
