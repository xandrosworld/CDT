$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$required = @(
    ".env",
    ".git",
    "_HANDOFF\ULTRA_HANDOFF_LAPTOP_2026-09-01.md",
    "tdp_system\server.py",
    "tdp_system\contract_modules.py",
    "tdp_system\data\tdp.sqlite3",
    "BAN_PC_TDP\TDP_Server.exe",
    "BAN_PC_TDP\data\tdp.sqlite3",
    "BUILD_PORTABLE.ps1"
)

foreach ($relativePath in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $relativePath))) {
        throw "Thieu file/thu muc bat buoc: $relativePath"
    }
}

$expectedHashes = @{
    "BAN_PC_TDP\TDP_Server.exe" = "F0B0EF564DDF1DE1B35390EAD629DF6AC01EA28E4C8CD71E19F2E04792643D71"
    "BAN_PC_TDP\data\tdp.sqlite3" = "C7E8A4EFE43B4270376C334E3A1BF00C3CFA79F8BD7BC7B1D789E6FE90E4E0C6"
}

foreach ($entry in $expectedHashes.GetEnumerator()) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $projectRoot $entry.Key)).Hash
    if ($actual -ne $entry.Value) {
        throw "Sai SHA256: $($entry.Key)"
    }
}

Write-Host "Du .env, Git, source, database va ban portable. Khong hien thi noi dung .env."
Write-Host "SHA256 cua EXE va database portable khop ban da QC tren PC."
Write-Host "Buoc tiep theo: doc BAT_DAU_TREN_LAPTOP.md roi chay unit test, QC va /health."
