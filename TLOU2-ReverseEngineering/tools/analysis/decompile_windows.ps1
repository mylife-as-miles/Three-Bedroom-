# Optional independent full decompilation. Never place output in publishable directories.
param([Parameter(Mandatory=$true)][string]$Dconstruct, [string]$ResearchRoot = (Resolve-Path "$PSScriptRoot/../.."))
$InputRoot = Join-Path $ResearchRoot '.private/extracted/dc1'
$OutputRoot = Join-Path $ResearchRoot '.private/dconstruct-output'
$Log = Join-Path $ResearchRoot '.private/checkpoints/dconstruct-batch.log'
New-Item -ItemType Directory -Force $OutputRoot | Out-Null
# Keep sidbase.bin next to the executable, as required by the pinned CLI.
& $Dconstruct -i $InputRoot -o $OutputRoot --no_optimize --emit_once *>&1 | Tee-Object -FilePath $Log
if ($LASTEXITCODE -ne 0) { throw "dconstruct failed; inspect $Log" }
Get-ChildItem $OutputRoot -Recurse -File | Group-Object Extension | Select-Object Name,Count
