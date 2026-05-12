# Stop and remove the FinAlly container on Windows.
# The 'finally-data' volume is preserved so the SQLite database survives.

$ErrorActionPreference = "Stop"

$ContainerName = "finally"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker is not installed or not on PATH"
    exit 1
}

$running = (docker ps -q -f "name=^${ContainerName}$")
if ($running) {
    Write-Host "Stopping container '$ContainerName'..."
    docker stop $ContainerName | Out-Null
}

$existing = (docker ps -aq -f "name=^${ContainerName}$")
if ($existing) {
    Write-Host "Removing container '$ContainerName'..."
    docker rm $ContainerName | Out-Null
}

Write-Host "Stopped. Volume 'finally-data' was preserved."
