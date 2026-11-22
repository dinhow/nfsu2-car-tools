# Restores the original car files from the backup made by install.ps1.
# Restaura os arquivos originais a partir do backup feito pelo install.ps1.
param(
    [Parameter(Mandatory = $true)][string]$Game,
    [string]$Car = "SENTRA"
)
$ErrorActionPreference = "Stop"
$backup = Join-Path $Game "_backup_$($Car.ToLower())_original"
if (-not (Test-Path $backup)) { throw "Backup not found: $backup" }
if (Get-Process -Name SPEED2 -ErrorAction SilentlyContinue) { throw "Close the game first / Feche o jogo antes." }
Get-ChildItem $backup -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($backup.Length + 1)
    Copy-Item $_.FullName (Join-Path $Game $rel) -Force
    Write-Host "restored: $rel"
}
Write-Host "Original files restored."
