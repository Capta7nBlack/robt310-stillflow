$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment. Install Python 3.11 or newer.' }
}
& $python -m pip install --disable-pip-version-check -r requirements.txt -c constraints.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the internet connection and retry.' }
Write-Host 'Open http://127.0.0.1:8000 in your browser. Press Ctrl+C here to stop.'
& $python -m stillflow serve
