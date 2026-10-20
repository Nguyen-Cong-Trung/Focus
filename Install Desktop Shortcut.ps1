param([string]$DestinationFolder = [Environment]::GetFolderPath('DesktopDirectory'))

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$executablePath = Join-Path $projectRoot 'Focus.exe'
if (Test-Path -LiteralPath $executablePath -PathType Leaf) {
    $targetPath = $executablePath
    $targetArguments = ''
    $iconPath = $executablePath
    $requiredPaths = @($targetPath)
} else {
    $targetPath = Join-Path $projectRoot '.runtime\Scripts\pythonw.exe'
    $mainPath = Join-Path $projectRoot 'PythonProject\main.py'
    $iconPath = Join-Path $projectRoot 'branding\focus.ico'
    $targetArguments = '-B "' + $mainPath + '"'
    $requiredPaths = @($targetPath, $mainPath, $iconPath)
}
foreach ($requiredPath in $requiredPaths) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required file missing: $requiredPath"
    }
}
if (-not (Test-Path -LiteralPath $DestinationFolder -PathType Container)) {
    throw "Shortcut folder does not exist: $DestinationFolder"
}
$shell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path $DestinationFolder 'Focus.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    $existing = $shell.CreateShortcut($shortcutPath)
    if ($existing.TargetPath -ne $targetPath -or $existing.Arguments -ne $targetArguments) {
        $shortcutPath = Join-Path $DestinationFolder ('Focus - ' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.lnk')
    }
}
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.Arguments = $targetArguments
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Focus - Spertulo Utility'
$shortcut.IconLocation = $iconPath + ',0'
$shortcut.WindowStyle = 1
$shortcut.Save()

$verified = $shell.CreateShortcut($shortcutPath)
if ($verified.TargetPath -ne $targetPath -or $verified.IconLocation -notlike "*$iconPath*") {
    throw 'Shortcut verification failed.'
}
# Remove only the old shortcut belonging to this project after verification.
$legacyPath = Join-Path $DestinationFolder 'Deep Focus.lnk'
if (Test-Path -LiteralPath $legacyPath) {
    $legacy = $shell.CreateShortcut($legacyPath)
    if ($legacy.TargetPath -eq $targetPath -and $legacy.Arguments -eq $targetArguments) {
        Remove-Item -LiteralPath $legacyPath
    }
}
[pscustomobject]@{
    Shortcut = $shortcutPath
    Target = $verified.TargetPath
    Arguments = $verified.Arguments
    Icon = $verified.IconLocation
}
