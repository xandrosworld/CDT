$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot
$masterSource = Get-ChildItem -LiteralPath $projectRoot -Filter "Em *.xlsx" -File | Select-Object -First 1
if (-not $masterSource) {
  throw "Khong tim thay file danh muc Em *.xlsx"
}
if (Test-Path -LiteralPath "dist\TDP_Server.exe") {
  Remove-Item -LiteralPath "dist\TDP_Server.exe" -Force
}

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name TDP_Server `
  --paths tdp_system `
  --add-data "tdp_system/static;static" `
  --add-data "demo_tdp/styles.css;shared" `
  --add-data "$($masterSource.FullName);." `
  tdp_system/server.py

if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath "dist\TDP_Server.exe")) {
  throw "Build portable that bai"
}
Write-Host "Da build: dist/TDP_Server.exe"
