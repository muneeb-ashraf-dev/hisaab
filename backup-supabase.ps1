#requires -Version 5.1
<#
.SYNOPSIS
    Create a public-schema backup of the database configured in backend/.env.

.DESCRIPTION
    Reads DATABASE_URL from backend/.env, removes the SQLAlchemy +psycopg
    driver prefix, and runs pg_dump in custom format. Only the public schema is
    included so the dump can be restored into a normal local PostgreSQL install.

    The newest 30 dumps are kept by default. The password is passed through the
    PGPASSWORD environment variable, not on the command line.

.EXAMPLE
    .\backup-supabase.ps1

.EXAMPLE
    .\backup-supabase.ps1 -Keep 60
#>
[CmdletBinding()]
param(
    [string]$EnvFile,
    [string]$BackupDirectory,
    [ValidateRange(1, 3650)]
    [int]$Keep = 30
)

$ErrorActionPreference = 'Stop'

if (-not $EnvFile) {
    $EnvFile = Join-Path $PSScriptRoot 'backend\.env'
}
if (-not $BackupDirectory) {
    $BackupDirectory = Join-Path $PSScriptRoot 'backups'
}

function Get-EnvValue {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [Parameter(Mandatory)]
        [string]$Name
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Environment file not found: $Path"
    }

    $line = Get-Content -LiteralPath $Path |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*=" } |
        Select-Object -First 1

    if (-not $line) {
        throw "$Name is not set in $Path"
    }

    $value = ($line -replace "^\s*$([regex]::Escape($Name))\s*=\s*", '').Trim()
    if ($value.Length -ge 2) {
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
    }

    return $value
}

function Find-PgDump {
    $command = Get-Command pg_dump.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe',
        'C:\Program Files\PostgreSQL\17\bin\pg_dump.exe',
        'C:\Program Files\PostgreSQL\16\bin\pg_dump.exe',
        'C:\Program Files\PostgreSQL\15\bin\pg_dump.exe'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw 'pg_dump.exe was not found. Add the PostgreSQL bin directory to PATH or install PostgreSQL.'
}

$databaseUrl = Get-EnvValue -Path $EnvFile -Name 'DATABASE_URL'
$nativeUrl = $databaseUrl -replace '^postgresql\+psycopg://', 'postgresql://'
if ($nativeUrl -notmatch '^postgresql://') {
    throw "DATABASE_URL must start with postgresql+psycopg:// or postgresql://. Current value is not supported."
}

$uri = [System.Uri]$nativeUrl
if (-not $uri.UserInfo) {
    throw 'DATABASE_URL does not contain a username and password.'
}

$userParts = $uri.UserInfo -split ':', 2
if ($userParts.Count -lt 2) {
    throw 'DATABASE_URL does not contain a password.'
}

$user = [System.Uri]::UnescapeDataString($userParts[0])
$password = [System.Uri]::UnescapeDataString($userParts[1])
$database = $uri.AbsolutePath.TrimStart('/')
if ([string]::IsNullOrWhiteSpace($database)) {
    $database = 'postgres'
}
$port = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }

$pgDump = Find-PgDump
New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupFile = Join-Path $BackupDirectory "supabase-public-$timestamp.dump"

$previousPassword = $env:PGPASSWORD
try {
    $env:PGPASSWORD = $password
    & $pgDump `
        -h $uri.Host `
        -p $port `
        -U $user `
        -d $database `
        --schema=public `
        --format=custom `
        --file=$backupFile

    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE."
    }
}
finally {
    if ($null -eq $previousPassword) {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    }
    else {
        $env:PGPASSWORD = $previousPassword
    }
}

$info = Get-Item -LiteralPath $backupFile
Write-Host "Backup created: $($info.FullName) ($([math]::Round($info.Length / 1KB, 1)) KB)"

$oldBackups = Get-ChildItem -LiteralPath $BackupDirectory -Filter 'supabase-public-*.dump' -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip $Keep

foreach ($oldBackup in $oldBackups) {
    Remove-Item -LiteralPath $oldBackup.FullName -Force
    Write-Host "Removed old backup: $($oldBackup.Name)"
}
