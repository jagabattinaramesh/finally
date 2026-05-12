# Start the FinAlly container on Windows.
#
# Usage:
#   powershell -File scripts\start_windows.ps1
#   powershell -File scripts\start_windows.ps1 -Build
#   powershell -File scripts\start_windows.ps1 -Open

[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$Open
)

$ErrorActionPreference = "Stop"

$ImageName     = "finally:latest"
$ContainerName = "finally"
$VolumeName    = "finally-data"
$Port          = 8000

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker is not installed or not on PATH"
    exit 1
}

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Error "No .env found. Copy .env.example to .env and add your OPENROUTER_API_KEY."
    } else {
        Write-Error "No .env file found at $RepoRoot\.env"
    }
    exit 1
}

function Image-Exists {
    docker image inspect $ImageName *> $null
    return ($LASTEXITCODE -eq 0)
}

if ($Build -or -not (Image-Exists)) {
    Write-Host "Building $ImageName..."
    docker build -t $ImageName .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$running = (docker ps -q -f "name=^${ContainerName}$")
if ($running) {
    Write-Host "Container '$ContainerName' already running."
} else {
    $existing = (docker ps -aq -f "name=^${ContainerName}$")
    if ($existing) {
        docker rm $ContainerName | Out-Null
    }
    Write-Host "Starting container '$ContainerName' on port $Port..."
    docker run -d `
        --name $ContainerName `
        --env-file .env `
        -v "${VolumeName}:/app/db" `
        -p "${Port}:8000" `
        --restart unless-stopped `
        $ImageName | Out-Null
}

$url = "http://localhost:$Port"
Write-Host "FinAlly is starting at $url"
Write-Host "Health check: $url/api/health"

if ($Open) {
    Start-Process $url
}
