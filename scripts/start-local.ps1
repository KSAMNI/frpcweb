param(
    [switch]$Rebuild,
    [int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$local = Join-Path $root 'tmp\local-test'
if (-not (Test-Path -LiteralPath $python)) {
    & python -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create Python virtual environment.' }
}
& $python -m pip install -r (Join-Path $root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
$dist = Join-Path $root 'frontend\dist\index.html'
if ($Rebuild -or -not (Test-Path -LiteralPath $dist)) {
    & npm --prefix (Join-Path $root 'frontend') ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    & npm --prefix (Join-Path $root 'frontend') run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}
New-Item -ItemType Directory -Path $local -Force | Out-Null
foreach ($name in @('frpc.toml', 'app_config.json')) {
    $destination = Join-Path $local $name
    if (-not (Test-Path -LiteralPath $destination)) {
        Copy-Item -LiteralPath (Join-Path $root $name) -Destination $destination
    }
}
$values = @{
    'FRPC_CONFIG' = (Join-Path $local 'frpc.toml')
    'APP_CONFIG' = (Join-Path $local 'app_config.json')
    'FRPC_LOG' = (Join-Path $local 'frpc.log')
    'FRPC_MANAGE' = '0'
    'FRPC_AUTOSTART' = '0'
    'HOST' = '127.0.0.1'
    'PORT' = [string]$Port
    'PYTHONDONTWRITEBYTECODE' = '1'
}
$previous = @{}
foreach ($key in $values.Keys) {
    $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
    [Environment]::SetEnvironmentVariable($key, $values[$key], 'Process')
}
try {
    Write-Host "Local preview: http://127.0.0.1:$Port"
    Write-Host "Using config COPIES in: $local"
    Write-Host 'FRPC process management is OFF. Press Ctrl+C to stop.'
    & $python -B (Join-Path $root 'main.py')
    if ($LASTEXITCODE -ne 0) { throw 'Local server exited with an error.' }
} finally {
    foreach ($key in $previous.Keys) {
        [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process')
    }
}
