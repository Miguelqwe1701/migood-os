# Joins the Migood OS ISO parts from a GitHub release back into one .iso and
# checks it against the .sha256 file. Windows version of merge-iso.sh.
# Easiest: put this, merge-iso.bat and all the parts in one folder, then
# double-click merge-iso.bat.
param([string]$Folder = $PSScriptRoot)
$ErrorActionPreference = "Stop"
Set-Location $Folder

$parts = Get-ChildItem -Filter "migood-os-*.iso.part*" | Sort-Object Name
if ($parts.Count -eq 0) {
    Write-Host "No migood-os-*.iso.part* files here. Download all the parts from the release first."
    exit 1
}
$iso = $parts[0].Name -replace '\.part\d+$', ''
Write-Host "Joining $($parts.Count) parts into $iso ..."
$out = [System.IO.File]::Create((Join-Path $Folder $iso))
try {
    foreach ($p in $parts) {
        Write-Host "  + $($p.Name)"
        $in = [System.IO.File]::OpenRead($p.FullName)
        try { $in.CopyTo($out) } finally { $in.Close() }
    }
} finally { $out.Close() }

$shaFile = "$iso.sha256"
if (Test-Path $shaFile) {
    Write-Host "Checking it (this takes a minute)..."
    $expected = ((Get-Content $shaFile -Raw).Trim() -split '\s+')[0].ToLower()
    $actual = (Get-FileHash $iso -Algorithm SHA256).Hash.ToLower()
    if ($expected -eq $actual) {
        Write-Host "Done: $iso is complete and correct. You can delete the .part files." -ForegroundColor Green
    } else {
        Write-Host "The check failed: a part is missing or didn't download fully. Download the parts again." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Done: $iso (no .sha256 file here, so it wasn't checked)."
}
