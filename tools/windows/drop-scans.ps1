param([string]$SettingsPath = (Join-Path $PSScriptRoot 'drop-settings.local.json'))
$ErrorActionPreference = 'Stop'
$contract = Get-Content -LiteralPath (Join-Path $PSScriptRoot '../../brownstone/drop_contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json

function Get-DropNameParts([string]$Name) {
    $match = [regex]::Match($Name, $contract.file_pattern)
    if (-not $match.Success -or $match.Length -ne $Name.Length) { return $null }
    $time = [datetime]::MinValue
    $ok = [datetime]::TryParseExact($match.Groups[2].Value, $contract.time_format,
        [cultureinfo]::InvariantCulture, [Globalization.DateTimeStyles]::None, [ref]$time)
    if (-not $ok) { return $null }
    return @{ Machine = $match.Groups[1].Value; Time = $time }
}

function Get-DropUtcTime { return [datetime]::UtcNow }

function Send-BrownstoneDrop {
    $settings = Get-Content -LiteralPath $SettingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not ($settings.machine -is [string])) { throw 'Machine must be text.' }
    $machineMatch = [regex]::Match($settings.machine, $contract.machine_pattern)
    if (-not $machineMatch.Success -or $machineMatch.Length -ne $settings.machine.Length) {
        throw 'Machine must contain only lowercase letters, digits and hyphens.'
    }
    if (Get-Process -Name 'Wow*' -ErrorAction SilentlyContinue) { throw 'Log out and close WoW before running this script.' }
    if (-not (Test-Path -LiteralPath $settings.saved_variables -PathType Leaf)) { throw 'SavedVariables file is missing.' }
    if (-not (Test-Path -LiteralPath $settings.drop_folder -PathType Container)) { throw 'Drop folder is missing or offline.' }
    $sourceHash = (Get-FileHash -LiteralPath $settings.saved_variables -Algorithm SHA256).Hash
    $latest = Get-ChildItem -LiteralPath $settings.drop_folder -File | ForEach-Object {
        $parts = Get-DropNameParts $_.Name
        if ($parts -and $parts.Machine -ceq $settings.machine) { $_ }
    } | Sort-Object Name -Descending | Select-Object -First 1
    if ($latest -and (Get-FileHash -LiteralPath $latest.FullName -Algorithm SHA256).Hash -eq $sourceHash) {
        Write-Output 'Nothing new: bytes match this machine''s latest drop.'
        return
    }
    $name = $contract.file_template.Replace('{machine}', $settings.machine).Replace(
        '{time}', (Get-DropUtcTime).ToString($contract.time_format, [cultureinfo]::InvariantCulture))
    $final = Join-Path $settings.drop_folder $name
    $temporary = $final + '.' + [guid]::NewGuid().ToString('N') + '.partial'
    # CreateNew and Move without overwrite protect both temporary and final names.
    try {
        $sourceStream = [IO.File]::Open($settings.saved_variables, 'Open', 'Read', 'Read')
        try {
            $copyStream = [IO.File]::Open($temporary, 'CreateNew', 'Write', 'None')
            try { $sourceStream.CopyTo($copyStream) } finally { $copyStream.Dispose() }
        } finally { $sourceStream.Dispose() }
        if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash -ne $sourceHash -or
            (Get-FileHash -LiteralPath $settings.saved_variables -Algorithm SHA256).Hash -ne $sourceHash) {
            throw 'Source changed or copy verification failed; no final drop published.'
        }
        [IO.File]::Move($temporary, $final)
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
    }
    Write-Output ('Verified drop: ' + $name + '. Import on the Mac before clearing in game.')
}

# Dot sourcing exposes functions for offline tests, without running a copy.
if ($MyInvocation.InvocationName -ne '.') {
    try { Send-BrownstoneDrop } catch { Write-Host ('Not copied: ' + $_.Exception.Message) -ForegroundColor Red; exit 1 }
}
