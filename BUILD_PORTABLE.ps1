$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$requiredSourceFiles = @(
  "tdp_system\pdf_documents.py",
  "tdp_system\print_bundle.py",
  "tdp_system\invoice_tax_export.py",
  "tdp_system\outgoing_substitution.py",
  "tdp_system\invoice_payment_scope.py",
  "tdp_system\invoice_payment_documents.py",
  "tdp_system\invoice_delivery_statement.py",
  "tdp_system\invoice_input_export.py",
  "tdp_system\invoice_workbench_listing.py",
  "tdp_system\invoice_date_migration.py",
  "tdp_system\physical_inventory.py",
  "tdp_system\document_totals.py",
  "tdp_system\round3_documents.py",
  "tdp_system\document_preview.py",
  "tdp_system\round4_documents.py",
  "tdp_system\static\document-preview.js",
  "tdp_system\static\invoice-workbench.js",
  "tdp_system\invoice_valuation.py",
  "tdp_system\inventory_export.py",
  "tdp_system\bk_import.py",
  "tdp_system\print_tools\SumatraPDF-3.6.1-64.exe",
  "tdp_system\print_tools\SUMATRA_NOTICE.txt"
)
foreach ($requiredSourceFile in $requiredSourceFiles) {
  if (-not (Test-Path -LiteralPath $requiredSourceFile -PathType Leaf)) {
    throw "Thieu module bat buoc khi build: $requiredSourceFile"
  }
}

$taxTemplateDir = Join-Path $projectRoot "bosung.30.8.26"
$taxTemplateFiles = @(
  "thue 0.xlsx",
  "thue 8.xlsx",
  "thue 10.xlsx",
  "thue 10 c$([char]0x00F3) khuy$([char]0x1EBF)n m$([char]0x1EA1)i.xlsx"
)
foreach ($taxTemplateFile in $taxTemplateFiles) {
  $taxTemplatePath = Join-Path $taxTemplateDir $taxTemplateFile
  if (-not (Test-Path -LiteralPath $taxTemplatePath -PathType Leaf)) {
    throw "Khong tim thay mau thue bat buoc: $taxTemplateFile"
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

$openingTemplateName = "T$([char]0x0110)K T8-2026.xlsx th$([char]0x1EE5)y.xlsx"
$openingTemplateSource = Join-Path $projectRoot "_HANDOFF\EXTERNAL_INPUTS\$openingTemplateName"
if (-not (Test-Path -LiteralPath $openingTemplateSource -PathType Leaf)) {
  throw "Khong tim thay mau TDK-NXT bat buoc: $openingTemplateName"
}
$openingTemplateSha256 = "36DF2BA86D13307F96BB5944FCECB19A4A81C093B4AC6A98EA71330D68204DA6"
$openingTemplateActualSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $openingTemplateSource).Hash
if ($openingTemplateActualSha256 -ne $openingTemplateSha256) {
  throw "Mau TDK-NXT sai SHA-256 da khoa; dung build de tranh backfill Ma kho sai"
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
  --hidden-import invoice_tax_export `
  --hidden-import outgoing_substitution `
  --hidden-import invoice_payment_scope `
  --hidden-import invoice_payment_documents `
  --hidden-import invoice_delivery_statement `
  --hidden-import invoice_input_export `
  --hidden-import invoice_workbench_listing `
  --hidden-import invoice_date_migration `
  --hidden-import physical_inventory `
  --hidden-import document_totals `
  --hidden-import round3_documents `
  --hidden-import document_preview `
  --hidden-import round4_documents `
  --hidden-import invoice_valuation `
  --hidden-import inventory_export `
  --hidden-import bk_import `
  --hidden-import pypdf `
  --hidden-import reportlab `
  --hidden-import reportlab.pdfbase._fontdata_widths_helvetica `
  --hidden-import reportlab.pdfbase._fontdata_widths_helveticabold `
  --hidden-import win32print `
  --add-data "tdp_system/static;static" `
  --add-binary "tdp_system/print_tools/SumatraPDF-3.6.1-64.exe;print_tools" `
  --add-data "tdp_system/print_tools/SUMATRA_NOTICE.txt;print_tools" `
  --add-data "demo_tdp/styles.css;shared" `
  --add-data "$masterSource;." `
  --add-data "$openingTemplateSource;." `
  --add-data "$taxTemplateDir\thue 0.xlsx;tax_templates" `
  --add-data "$taxTemplateDir\thue 8.xlsx;tax_templates" `
  --add-data "$taxTemplateDir\thue 10.xlsx;tax_templates" `
  --add-data "$taxTemplateDir\thue 10 c$([char]0x00F3) khuy$([char]0x1EBF)n m$([char]0x1EA1)i.xlsx;tax_templates" `
  tdp_system/server.py

if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath "dist\TDP_Server_candidate.exe")) {
  throw "Build portable that bai"
}
$releasePath = Join-Path $projectRoot "dist\TDP_Server.exe"
if (Test-Path -LiteralPath $releasePath -PathType Leaf) {
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $backupPath = Join-Path $projectRoot "dist\TDP_Server.pre_build_$stamp.exe"
  Move-Item -LiteralPath $releasePath -Destination $backupPath
  Write-Host "Da giu EXE cu: $backupPath"
}
Move-Item -LiteralPath "dist\TDP_Server_candidate.exe" -Destination "dist\TDP_Server.exe"
Write-Host "Da build: dist/TDP_Server.exe"
