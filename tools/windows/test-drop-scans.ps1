# Offline test harness: no Pester or other installation required.
param([Parameter(Mandatory=$true)][string]$TestRoot)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'drop-scans.ps1')
function Assert-True($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
foreach ($example in $contract.examples) {
    $parsed = Get-DropNameParts $example.name
    Assert-True ([bool]$parsed -eq $example.valid) ('Naming disagreement: ' + $example.name)
}
New-Item -ItemType Directory -Path $TestRoot -Force | Out-Null
$source = Join-Path $TestRoot 'BrownstoneScan.lua'
$folder = Join-Path $TestRoot 'drop'
New-Item -ItemType Directory -Path $folder | Out-Null
[IO.File]::WriteAllBytes($source, [byte[]](0, 10, 13, 255, 42))
$sourceHash = (Get-FileHash -LiteralPath $source).Hash
$settings = Join-Path $TestRoot 'settings.json'
@{saved_variables=$source; drop_folder=$folder; machine='windows-pc'} |
    ConvertTo-Json | Set-Content -LiteralPath $settings -Encoding UTF8
$SettingsPath = $settings
# Stub the process check; neither the test runner nor a real game is consulted.
function Get-Process { return $null }
function Get-DropUtcTime { return [datetime]::Parse('2026-10-07T00:49:00Z').ToUniversalTime() }
$result = Send-BrownstoneDrop
Assert-True ($result -like 'Verified drop:*') 'Expected verified copy'
$files = @(Get-ChildItem -LiteralPath $folder -File)
Assert-True ($files.Count -eq 1) 'Expected exactly one final file'
Assert-True ([bool](Get-DropNameParts $files[0].Name)) 'Final name invalid'
Assert-True ((Get-FileHash -LiteralPath $files[0].FullName).Hash -eq $sourceHash) 'Copied bytes differ'
$result = Send-BrownstoneDrop
Assert-True ($result -like 'Nothing new:*') 'Identical source should be skipped'
Assert-True (@(Get-ChildItem -LiteralPath $folder -File).Count -eq 1) 'Duplicate wrote a file'
Assert-True ((Get-FileHash -LiteralPath $source).Hash -eq $sourceHash) 'Source modified'
# Missing source, game running, invalid machine, and copy/hash verification failure.
function Expect-Failure([string]$Pattern) {
    $failure = $null
    try { Send-BrownstoneDrop } catch { $failure = $_ }
    Assert-True ($null -ne $failure) 'Expected failure'
    Assert-True ($failure.Exception.Message -like $Pattern) ('Unexpected error: ' + $failure)
}
function Get-Process { return @{ProcessName='Wow'} }
Expect-Failure '*close WoW*'
function Get-Process { return $null }
$missing = Join-Path $TestRoot 'missing.lua'
@{saved_variables=$missing; drop_folder=$folder; machine='pc'} | ConvertTo-Json | Set-Content $settings -Encoding UTF8
Expect-Failure '*missing*'
foreach ($machine in @('PC', 'pc_1', '', "pc`n")) {
    @{saved_variables=$source; drop_folder=$folder; machine=$machine} | ConvertTo-Json | Set-Content $settings -Encoding UTF8
    Expect-Failure '*Machine must*'
}
@{saved_variables=$source; drop_folder=$folder; machine='second-pc'} | ConvertTo-Json | Set-Content $settings -Encoding UTF8
function Get-FileHash {
    param([string]$LiteralPath, [string]$Algorithm)
    if ($LiteralPath -like '*.partial') { return @{Hash='wrong'} }
    return Microsoft.PowerShell.Utility\Get-FileHash -LiteralPath $LiteralPath -Algorithm SHA256
}
Expect-Failure '*verification failed*'
Assert-True (@(Get-ChildItem $folder -Filter '*.partial').Count -eq 0) 'Temporary copy not cleaned up'
Remove-Item function:Get-FileHash
# A changed source in the same timestamp cannot replace the earlier final drop.
@{saved_variables=$source; drop_folder=$folder; machine='windows-pc'} | ConvertTo-Json | Set-Content $settings -Encoding UTF8
[IO.File]::WriteAllText($source, 'changed bytes')
$changedHash = (Get-FileHash -LiteralPath $source).Hash
Expect-Failure '*'
Assert-True ((Get-FileHash -LiteralPath $files[0].FullName).Hash -eq $sourceHash) 'Collision overwritten'
Assert-True ((Get-FileHash -LiteralPath $source).Hash -eq $changedHash) 'Source modified'
Assert-True (@(Get-ChildItem $folder -Filter '*.partial').Count -eq 0) 'Collision temporary copy not cleaned'
Write-Output 'PASS: shared names, exact bytes, nothing new, game/missing/invalid guards, hash failure, no overwrite.'
