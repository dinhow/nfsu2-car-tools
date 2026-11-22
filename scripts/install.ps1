# Installs the generated car files into NFSU2, backing up the originals on the first run.
# Instala os arquivos gerados no NFSU2, com backup dos originais na primeira vez.
#
# Usage / Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -Game "C:\Games\Need for Speed Underground 2" [-Source out_game] [-Car SENTRA]
param(
    [Parameter(Mandatory = $true)][string]$Game,
    [string]$Source = (Join-Path $PSScriptRoot "..\out_game"),
    [string]$Car = "SENTRA"
)
$ErrorActionPreference = "Stop"
$files = @("CARS\$Car\GEOMETRY.BIN", "CARS\$Car\TEXTURES.BIN", "GLOBAL\GLOBALB.BUN", "GLOBAL\GlobalB.lzc")
$backup = Join-Path $Game "_backup_$($Car.ToLower())_original"

if (-not (Test-Path (Join-Path $Game "SPEED2.EXE"))) { throw "SPEED2.EXE not found in $Game" }
if (Get-Process -Name SPEED2 -ErrorAction SilentlyContinue) { throw "Close the game first / Feche o jogo antes." }

# backup only once, so a modified file never overwrites the original backup
if (-not (Test-Path $backup)) {
    foreach ($f in $files) {
        $dst = Join-Path $backup $f
        New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
        Copy-Item (Join-Path $Game $f) $dst
    }
    Write-Host "Backup: $backup"
} else {
    Write-Host "Backup already exists (kept): $backup"
}
foreach ($f in $files) {
    $src = Join-Path $Source $f
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $Game $f) -Force
        Write-Host "installed: $f"
    } else {
        Write-Host "skipped (not generated): $f"
    }
}
Write-Host "Done. Test OFFLINE first / Teste OFFLINE primeiro."
