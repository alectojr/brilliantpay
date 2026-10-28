param(
    [string]$BackupDirectory = ".\backups"
)

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
Copy-Item ".\brilliantpay.db" "$BackupDirectory\brilliantpay-$timestamp.db" -ErrorAction Stop
if (Test-Path ".\static\uploads") {
    Compress-Archive -Path ".\static\uploads\*" -DestinationPath "$BackupDirectory\uploads-$timestamp.zip" -Force
}
Write-Output "Backup created in $BackupDirectory"
