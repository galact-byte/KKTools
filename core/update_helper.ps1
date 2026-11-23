$ErrorActionPreference = 'Stop'
$stage = [IO.Path]::GetFullPath($PSScriptRoot)
$backup = Join-Path $stage 'previous.exe'
$swapped = $false
$ok = $false
$reason = ''
$target = $null

try {
    $plan = [IO.File]::ReadAllText((Join-Path $stage 'plan.json'), [Text.Encoding]::UTF8) | ConvertFrom-Json
    $target = [IO.Path]::GetFullPath($plan.target)
    $source = [IO.Path]::GetFullPath($plan.source)
    $root = [IO.Path]::GetDirectoryName($target)
    $expectedParent = [IO.Path]::Combine($root, '.kktools-update')
    if ([IO.Path]::GetDirectoryName($stage) -ne $expectedParent -or
        [IO.Path]::GetDirectoryName($source) -ne $stage -or
        [IO.Path]::GetExtension($target) -ne '.exe' -or
        [IO.Path]::GetFileName($source) -ne 'KKTools.exe') {
        throw 'Invalid update file locations.'
    }

    $parent = Get-Process -Id $plan.parent_pid -ErrorAction SilentlyContinue
    if ($null -ne $parent -and -not $parent.WaitForExit(600000)) {
        throw 'The application did not exit in time. Update cancelled.'
    }
    $file = Get-Item -LiteralPath $source
    $hash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    if ($file.Length -ne $plan.size -or $hash -ne $plan.sha256) {
        throw 'Downloaded program changed after verification. Update cancelled.'
    }

    for ($i = 0; $i -lt 40; $i++) {
        try {
            [IO.File]::Replace($source, $target, $backup)
            $swapped = $true
            break
        } catch {
            if ($i -eq 39) { throw }
            Start-Sleep -Milliseconds 250
        }
    }
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $target
    $start.WorkingDirectory = $root
    $start.UseShellExecute = $false
    $app = [Diagnostics.Process]::Start($start)
    if ($app.WaitForExit(2000)) { throw 'The updated application exited immediately.' }
    $ok = $true
    [IO.File]::Delete($backup)
} catch {
    $reason = $_.Exception.Message
    if ($swapped -and (Test-Path -LiteralPath $backup)) {
        try {
            [IO.File]::Replace($backup, $target, (Join-Path $stage 'failed.exe'))
            $start = New-Object Diagnostics.ProcessStartInfo
            $start.FileName = $target
            $start.WorkingDirectory = [IO.Path]::GetDirectoryName($target)
            $start.UseShellExecute = $false
            [Diagnostics.Process]::Start($start) | Out-Null
        } catch {
            $reason += ' Rollback needs manual recovery from: ' + $backup + ' (' + $_.Exception.Message + ')'
        }
    }
} finally {
    if ($null -ne $target) {
        try {
            $result = @{ ok = $ok; reason = $reason; version = $plan.version; time = [DateTime]::UtcNow.ToString('o') } | ConvertTo-Json
            $resultPath = Join-Path ([IO.Path]::GetDirectoryName($target)) '.kktools-update-result.json'
            [IO.File]::WriteAllText($resultPath, $result, (New-Object Text.UTF8Encoding $false))
        } catch {}
    }
    if (-not (Test-Path -LiteralPath $backup)) {
        Set-Location ([IO.Path]::GetTempPath())
        [Environment]::CurrentDirectory = [IO.Path]::GetTempPath()
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    }
}
if (-not $ok) { exit 1 }
