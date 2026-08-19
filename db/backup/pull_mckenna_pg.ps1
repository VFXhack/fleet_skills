# pull_mckenna_pg.ps1 — watts side of ADR 0025's backup story.
# Pulls mckenna's nightly pg dumps to E:\backups\mckenna_pg and prunes local
# copies older than 30 days. Registered as scheduled task 'FleetPgBackupPull'
# (04:00 nightly — after mckenna's 02:30 dump).
$dest = 'E:\backups\mckenna_pg'
New-Item -ItemType Directory -Force $dest | Out-Null
scp -o BatchMode=yes "andy@mckenna:/mnt/shared/pg_backups/*.dump" $dest
$cutoff = (Get-Date).AddDays(-30)
Get-ChildItem $dest -Filter *.dump | Where-Object { $_.LastWriteTime -lt $cutoff } |
    Remove-Item -Force -Confirm:$false
"pulled $(Get-Date -Format s); files: $((Get-ChildItem $dest -Filter *.dump).Count)" |
    Out-File -Append -Encoding utf8 (Join-Path $dest 'pull.log')
