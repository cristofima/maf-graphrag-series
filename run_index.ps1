# GraphRAG Indexing Script with Windows UTF-8 Fix
# Loads .env variables and runs indexing with proper encoding

# Get the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Set UTF-8 encoding for PowerShell console output
$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding

# Set Python UTF-8 mode
$env:PYTHONUTF8 = 1

# Load .env file
Get-Content (Join-Path $ScriptDir ".env") | ForEach-Object {
    if ($_ -match '^([^=# ]+)=(.*)$') {
        $name = $matches[1]
        $value = $matches[2]
        [System.Environment]::SetEnvironmentVariable($name, $value, 'Process')
        Write-Host "Loaded: $name" -ForegroundColor Green
    }
}

# Detect Poetry or venv
Write-Host "`nStarting GraphRAG indexing..." -ForegroundColor Cyan

if (Get-Command poetry -ErrorAction SilentlyContinue) {
    Write-Host "✓ Using Poetry environment" -ForegroundColor Green
    poetry run python -m graphrag index --root $ScriptDir
} elseif (Test-Path (Join-Path $ScriptDir ".venv\Scripts\python.exe")) {
    Write-Host "⚠ Using legacy virtualenv (.venv) - Consider migrating to Poetry" -ForegroundColor Yellow
    $VenvPath = Join-Path $ScriptDir ".venv\Scripts\python.exe"
    & $VenvPath -m graphrag index --root $ScriptDir
} else {
    Write-Host "`n❌ ERROR: Poetry not found and no virtualenv available" -ForegroundColor Red
    Write-Host "`nThis project uses Poetry for dependency management. Install it:" -ForegroundColor Yellow
    Write-Host "`n  1. Install Poetry:" -ForegroundColor Cyan
    Write-Host "     (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -" -ForegroundColor White
    Write-Host "`n  2. Install dependencies:" -ForegroundColor Cyan
    Write-Host "     poetry install" -ForegroundColor White
    Write-Host "`n  3. Run this script again" -ForegroundColor Cyan
    Write-Host "`nSee docs/poetry-guide.md for more information.`n" -ForegroundColor Gray
    exit 1
}
