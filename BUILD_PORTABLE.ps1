$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$requiredSourceFiles = @(
  "tdp_system\pdf_documents.py",
  "tdp_system\print_bundle.py"
)
foreach ($requiredSourceFile in $requiredSourceFiles) {
  if (-not (Test-Path -LiteralPath $requiredSourceFile -PathType Leaf)) {
    throw "Thieu module bat buoc khi build: $requiredSourceFile"
  }
}

# Fail before PyInstaller does expensive work when the build environment is
# missing a runtime dependency used only by the PDF/Windows print paths.
python -c "import pypdf, reportlab, win32print"
if ($LASTEXITCODE -ne 0) {
  throw "Thieu dependency PDF/may in; hay cai tdp_system/requirements.txt"
}

$masterName = "Em Th$([char]0x00E0)nh.xlsx"
$masterSource = Join-Path $projectRoot $masterName
if (-not (Test-Path -LiteralPath $masterSource -PathType Leaf)) {
  throw "Khong tim thay dung file danh muc bat buoc: $masterName"
}

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name TDP_Server_candidate `
  --paths tdp_system `
  --hidden-import pdf_documents `
  --hidden-import print_bundle `
  --hidden-import xcom_payment_documents `
  --hidden-import pypdf `
  --hidden-import reportlab `
  --hidden-import reportlab.pdfbase._fontdata_widths_helvetica `
  --hidden-import reportlab.pdfbase._fontdata_widths_helveticabold `
  --hidden-import win32print `
  --add-data "tdp_system/static;static" `
  --add-data "demo_tdp/styles.css;shared" `
  --add-data "$masterSource;." `
  tdp_system/server.py

if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath "dist\TDP_Server_candidate.exe")) {
  throw "Build portable that bai"
}
Move-Item -LiteralPath "dist\TDP_Server_candidate.exe" -Destination "dist\TDP_Server.exe" -Force
Write-Host "Da build: dist/TDP_Server.exe"
