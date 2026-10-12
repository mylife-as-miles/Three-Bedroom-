# Offline build/static checks only. Never writes to a game installation or starts TLOU2.
param(
    [Parameter(Mandatory=$true)][string]$InputDc1,
    [Parameter(Mandatory=$true)][string]$Vendor,
    [Parameter(Mandatory=$true)][string]$CtreHeaderDir,
    [string]$Actor = 'drawer-wat-kitchen-apartment-1'
)
$ErrorActionPreference = 'Stop'
$Experiment = $PSScriptRoot
$Research = (Resolve-Path (Join-Path $Experiment '../../..')).Path
$Scratch = Join-Path $Research '.private/experiments/drawer-diagnostics'
$Inputs = Join-Path $Scratch 'inputs/dc1'
$Tools = Join-Path $Scratch 'windows-toolchain'
function Run-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
New-Item -ItemType Directory -Force (Join-Path $Inputs 'ss-t2') | Out-Null
$SourceDrawer = (Resolve-Path (Join-Path $InputDc1 'ss-t2/ss-openable-drawer.bin')).Path
$SourceModules = (Resolve-Path (Join-Path $InputDc1 'modules.bin')).Path
$SourceHashes = @((Get-FileHash $SourceDrawer -Algorithm SHA256).Hash, (Get-FileHash $SourceModules -Algorithm SHA256).Hash)
if ($SourceHashes[0].ToLowerInvariant() -ne 'b69fb082a493a76a97405b052542047e530ae4d6da33ca15787114a487e3a0a5') { throw 'Wrong 1.6 drawer source hash' }
# Copy local user-owned inputs, not their decompiled source, into ignored scratch.
Copy-Item $SourceDrawer (Join-Path $Inputs 'ss-t2/ss-openable-drawer.bin') -Force
Copy-Item $SourceModules (Join-Path $Inputs 'modules.bin') -Force
Run-Checked 'cmake' @('-S', $Experiment, '-B', $Tools, '-G', 'Visual Studio 17 2022', '-A', 'x64', "-DDCONSTRUCT_VENDOR=$Vendor", "-DCTRE_HEADER_DIR=$CtreHeaderDir")
Run-Checked 'cmake' @('--build', $Tools, '--config', 'Release', '--target', 'compile_core', 'dconstruct')
$Compiler = Join-Path $Tools 'Release/compile_core.exe'
$Decompiler = Join-Path $Tools 'Release/dconstruct.exe'
Run-Checked 'python' @((Join-Path $Experiment 'roundtrip.py'), '--compiler', $Compiler, '--dconstruct', $Decompiler, '--output', (Join-Path $Scratch 'roundtrip-windows'))
$Output = Join-Path $Scratch 'build'
$Drawer = Join-Path $Inputs 'ss-t2/ss-openable-drawer.bin'
$Modules = Join-Path $Inputs 'modules.bin'
Run-Checked 'python' @((Join-Path $Experiment 'build.py'), '--original', $Drawer, '--modules', $Modules, '--compiler', $Compiler, '--dconstruct', $Decompiler, '--vendor', $Vendor, '--output', $Output, '--actor', $Actor)
Run-Checked 'python' @((Join-Path $Experiment 'validate_experiment.py'), '--original', $Drawer, '--modules', $Modules, '--build', $Output, '--report', (Join-Path $Output 'static-validation.json'))
Run-Checked 'python' @((Join-Path $Experiment 'test_static.py'), '--original', $Drawer, '--modules', $Modules, '--build', $Output)
$AfterHashes = @((Get-FileHash $SourceDrawer -Algorithm SHA256).Hash, (Get-FileHash $SourceModules -Algorithm SHA256).Hash)
if (Compare-Object $SourceHashes $AfterHashes) { throw 'Original source hashes changed' }
Get-FileHash (Join-Path $Output 'mod/bin/dc1/ss-t2/ss-openable-drawer.bin') -Algorithm SHA256
Write-Host "Static build complete under $Output. Game tests NOT RUN. Deployment is a separate authorized step."
