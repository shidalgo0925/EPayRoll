#!/usr/bin/env pwsh
# Aplica migraciones SQL en orden
param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [switch]$Docker
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$MigrationsDir = Join-Path $Root "database\migrations"

if (-not $DatabaseUrl) {
    $DatabaseUrl = "postgresql://epayroll:epayroll@localhost:5432/epayroll"
}

function Invoke-Psql {
    param([string]$Sql, [string]$File)
    if ($Docker) {
        if ($File) {
            Get-Content $File -Raw | docker exec -i epayroll-db psql -U epayroll -d epayroll -v ON_ERROR_STOP=1
        } else {
            $Sql | docker exec -i epayroll-db psql -U epayroll -d epayroll -v ON_ERROR_STOP=1
        }
    } else {
        $env:PGPASSWORD = ($DatabaseUrl -split ':')[2] -replace '@.*',''
        if ($File) {
            psql $DatabaseUrl -v ON_ERROR_STOP=1 -f $File
        } else {
            $Sql | psql $DatabaseUrl -v ON_ERROR_STOP=1
        }
    }
}

Write-Host "EPayRoll — aplicando migraciones..." -ForegroundColor Cyan

$files = Get-ChildItem $MigrationsDir -Filter "*.sql" | Sort-Object Name
foreach ($f in $files) {
    $version = $f.BaseName
    Write-Host "  → $version" -ForegroundColor Gray
    Invoke-Psql -File $f.FullName
    $insert = "INSERT INTO schema_migrations (version) VALUES ('$version') ON CONFLICT DO NOTHING;"
    Invoke-Psql -Sql $insert
}

Write-Host "Migraciones completadas." -ForegroundColor Green
Write-Host "Ejecutar seed: python scripts/seed.py"
