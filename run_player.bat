@echo off
echo Starting the Dual Subtitle Video Player...
echo The server will be available at http://localhost:8000

REM Check for any container using port 8000 and stop it
echo Checking for existing containers on port 8000...
for /f "tokens=*" %%i in ('docker ps -q --filter "publish=8000"') do (
    echo Stopping conflicting container %%i...
    docker stop %%i >nul 2>&1
)

echo Starting new player container...
docker run -it --rm --name psl-youtube-player -p 8000:8000 -v "D:\PSL_Downloads:/app/downloads" -v "%cd%:/app" python:3.11-slim python -u /app/player/server.py

pause
