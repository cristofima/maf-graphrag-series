# GraphRAG Query Runner
# Usage: .\run_query.ps1 -Method local -Query "Your question"

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("local", "global", "drift", "basic")]
    [string]$Method,
    
    [Parameter(Mandatory=$true)]
    [string]$Query
)

# Get the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Set UTF-8 encoding
$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$env:PYTHONUTF8 = 1

# Load .env file
Get-Content (Join-Path $ScriptDir ".env") | ForEach-Object {
    if ($_ -match '^([^=# ]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
        Write-Host "Loaded: $matches[1]" -ForegroundColor Green
    }
}

# Run GraphRAG query
Write-Host "`nRunning $Method search..." -ForegroundColor Cyan
Write-Host "Query: $Query`n" -ForegroundColor Yellow

$VenvPath = Join-Path $ScriptDir ".venv\Scripts\python.exe"
& $VenvPath -m graphrag query `
    --method $Method `
    --query $Query `
    --root $ScriptDir `
    --data "$ScriptDir\output" `
    --community-level 2 `
    --response-type "Multiple Paragraphs"
