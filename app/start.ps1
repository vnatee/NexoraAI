# set the parent of the script as the current location.
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "Loading azd .env file from current environment"
Write-Host ""

foreach ($line in (& azd env get-values)) {
    if ($line -match "([^=]+)=(.*)") {
        $key = $matches[1]
        $value = $matches[2] -replace '^"|"$'
        Set-Item -Path "env:\$key" -Value $value
    }
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to load environment variables from azd environment"
    exit $LASTEXITCODE
}

# Default only local development to the private filesystem attachment adapter.
# An explicitly configured environment (including Azure) still wins.
if (-not $env:CHAT_ATTACHMENT_STORE) {
    $env:CHAT_ATTACHMENT_STORE = "local"
}
if ($env:CHAT_ATTACHMENT_STORE -eq "local" -and -not $env:CHAT_ATTACHMENT_LOCAL_PATH) {
    $env:CHAT_ATTACHMENT_LOCAL_PATH = Join-Path (Split-Path $PSScriptRoot -Parent) ".data/chat-attachments"
}


Write-Host 'Creating python virtual environment ".venv"'
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
  # fallback to python3 if python not found
  $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}
Start-Process -FilePath ($pythonCmd).Source -ArgumentList "-m venv .venv" -Wait -NoNewWindow

Write-Host ""
Write-Host "Restoring backend python packages"
Write-Host ""

$directory = Get-Location
$venvPythonPath = "$directory/.venv/scripts/python.exe"
if (Test-Path -Path "/usr") {
  # fallback to Linux venv path
  $venvPythonPath = "$directory/.venv/bin/python"
}

Start-Process -FilePath $venvPythonPath -ArgumentList "-m pip install -r backend/requirements.txt" -Wait -NoNewWindow
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to restore backend python packages"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Restoring frontend npm packages"
Write-Host ""
Set-Location ./frontend
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to restore frontend npm packages"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Building frontend"
Write-Host ""
npm run build:memory-safe
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build frontend"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Starting backend"
Write-Host ""
Set-Location ../backend

$port = 50505
$hostname = "localhost"
Start-Process -FilePath $venvPythonPath -ArgumentList "-m quart --app main:app run --port $port --host $hostname --reload" -Wait -NoNewWindow

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start backend"
    exit $LASTEXITCODE
}
