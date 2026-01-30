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

# Run GraphRAG indexing
Write-Host "`nStarting GraphRAG indexing..." -ForegroundColor Cyan
$VenvPath = Join-Path $ScriptDir ".venv\Scripts\python.exe"
& $VenvPath -m graphrag index --root $ScriptDir
