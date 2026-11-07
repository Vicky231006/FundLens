# PowerShell task runner mirroring the Makefile (for Windows machines without GNU make).
#   .\make.ps1 reproduce
param([Parameter(Position = 0)][string]$Target = "help")

$ErrorActionPreference = "Stop"
$py = ".venv\Scripts\python.exe"

function Run([string]$cmd) {
    Write-Host ">> $cmd" -ForegroundColor Cyan
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE`: $cmd" }
}

switch ($Target) {
    "help"      { Get-Content $PSCommandPath | Select-String '^\s+"[a-z-]+"\s+\{' | ForEach-Object { $_.Line.Trim() } }
    "setup"     { Run "python -m venv .venv"; Run "$py -m pip install -e `".[dev]`"" }
    "db-up"     { Run "docker compose up -d db" }
    "db-down"   { Run "docker compose down" }
    "migrate"   { Run "$py -m fundlens.cli migrate" }
    "ingest"    { Run "$py -m fundlens.cli ingest" }
    "dq"        { Run "$py -m fundlens.cli dq" }
    "marts"     { Run "$py -m fundlens.cli build-marts" }
    "pipeline"  { Run "$py -m fundlens.cli pipeline" }
    "test-unit" { Run "$py -m pytest tests/unit tests/property -q" }
    "test"      { Run "$py -m pytest -q" }
    "lint"      { Run "$py -m ruff check src tests"; Run "$py -m ruff format --check src tests" }
    "format"    { Run "$py -m ruff format src tests" }
    "reproduce" {
        & $PSCommandPath db-up
        & $PSCommandPath migrate
        & $PSCommandPath ingest
        & $PSCommandPath pipeline
        Write-Host "Done. See RESULTS.md and results/." -ForegroundColor Green
    }
    default     { throw "Unknown target '$Target'. Run .\make.ps1 help" }
}
