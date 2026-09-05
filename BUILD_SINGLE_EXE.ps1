$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot
$masterName = "Em Th$([char]0x00E0)nh.xlsx"

# Co the dua toan bo file trung gian sang o dia con trong bang cach dat
# TDP_BUILD_WORK_ROOT (vi du D:\TDP_BUILD_WORK). TDP_RELEASE_DIR cho phep
# dua ca file ban giao sang o D ma khong ghi de ban cu.
$buildWorkRoot = $projectRoot
if (-not [string]::IsNullOrWhiteSpace($env:TDP_BUILD_WORK_ROOT)) {
  $buildWorkRoot = [IO.Path]::GetFullPath($env:TDP_BUILD_WORK_ROOT)
}
$buildDistDir = Join-Path $buildWorkRoot "dist\single_exe"
$buildWorkDir = Join-Path $buildWorkRoot "build\single_exe"
$buildSpecDir = Join-Path $buildWorkRoot "build\single_exe_spec"
New-Item -ItemType Directory -Path $buildDistDir -Force | Out-Null
New-Item -ItemType Directory -Path $buildWorkDir -Force | Out-Null
New-Item -ItemType Directory -Path $buildSpecDir -Force | Out-Null

$requiredSourceFiles = @(
  "tdp_system\server.py",
  "tdp_system\static\index.html",
  "tdp_system\static\app.js",
  "tdp_system\static\invoice-workbench.js",
  "tdp_system\static\real.css",
  "tdp_system\pdf_documents.py",
  "tdp_system\excel_print_renderer.py",
  "tdp_system\print_bundle.py",
  "tdp_system\invoice_tax_export.py",
  "tdp_system\outgoing_substitution.py",
  "tdp_system\invoice_payment_scope.py",
  "tdp_system\invoice_payment_documents.py",
  "tdp_system\invoice_delivery_statement.py",
  "tdp_system\invoice_input_export.py",
  "tdp_system\invoice_input_sync.py",
  "tdp_system\invoice_output_sync.py",
  "tdp_system\invoice_workbench.py",
  "tdp_system\invoice_workbench_listing.py",
  "tdp_system\invoice_date_migration.py",
  "tdp_system\physical_inventory.py",
  "tdp_system\document_totals.py",
  "tdp_system\round3_documents.py",
  "tdp_system\document_preview.py",
  "tdp_system\automatic_backup.py",
  "tdp_system\seller_identity_catalog.py",
  "tdp_system\receipt_export.py",
  "tdp_system\purchase_summary_export.py",
  "tdp_system\round4_documents.py",
  "tdp_system\static\document-preview.js",
  "tdp_system\minvoice_client.py",
  "tdp_system\invoice_valuation.py",
  "tdp_system\inventory_export.py",
  "tdp_system\inventory_period_close.py",
  "tdp_system\bk_import.py",
  "tdp_system\print_tools\SumatraPDF-3.6.1-64.exe",
  "tdp_system\print_tools\SUMATRA_NOTICE.txt",
  "tdp_system\templates\daily_order_template.xlsx",
  "tdp_system\templates\simple_payment_request_template.docx",
  "tdp_system\templates\bot_payment_template.xlsx",
  "tdp_system\templates\payroll_template.xlsx",
  "tdp_system\templates\seller_identities_20260904.xlsx",
  "demo_tdp\styles.css",
  $masterName,
  ".env",
  "tdp_system\data\tdp.sqlite3"
)
foreach ($requiredSourceFile in $requiredSourceFiles) {
  if (-not (Test-Path -LiteralPath $requiredSourceFile -PathType Leaf)) {
    throw "Thieu file bat buoc khi build: $requiredSourceFile"
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
  if (-not (Test-Path -LiteralPath (Join-Path $taxTemplateDir $taxTemplateFile) -PathType Leaf)) {
    throw "Khong tim thay mau thue bat buoc: $taxTemplateFile"
  }
}

$openingTemplateName = "T$([char]0x0110)K T8-2026.xlsx th$([char]0x1EE5)y.xlsx"
$openingTemplateSource = Join-Path $projectRoot "_HANDOFF\EXTERNAL_INPUTS\$openingTemplateName"
if (-not (Test-Path -LiteralPath $openingTemplateSource -PathType Leaf)) {
  throw "Khong tim thay mau kho bat buoc: $openingTemplateName"
}
$openingTemplateSha256 = "36DF2BA86D13307F96BB5944FCECB19A4A81C093B4AC6A98EA71330D68204DA6"
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $openingTemplateSource).Hash -ne $openingTemplateSha256) {
  throw "Mau kho sai SHA-256 da khoa; dung build"
}

python -c "import pypdf, reportlab, pythoncom, win32com.client, win32print, waitress, PyInstaller"
if ($LASTEXITCODE -ne 0) {
  throw "Thieu dependency build/PDF/may in"
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$releaseInputDir = Join-Path $tempBase ("tdp_single_exe_" + [guid]::NewGuid().ToString("N"))
$resolvedInputDir = [IO.Path]::GetFullPath($releaseInputDir)
$safeTempPrefix = $tempBase.TrimEnd('\') + '\'
if (-not $resolvedInputDir.StartsWith($safeTempPrefix, [StringComparison]::OrdinalIgnoreCase) -or
    -not (Split-Path -Leaf $resolvedInputDir).StartsWith("tdp_single_exe_")) {
  throw "Thu muc build tam khong an toan"
}

try {
  python -X utf8 tdp_system\build_release_inputs.py `
    --database "tdp_system\data\tdp.sqlite3" `
    --env-file ".env" `
    --output-dir "$resolvedInputDir"
  if ($LASTEXITCODE -ne 0) {
    throw "Khong tao duoc du lieu build an toan"
  }

  $masterSource = Join-Path $projectRoot $masterName
  python -m PyInstaller `
    --noconfirm `
    --clean `
    --noupx `
    --onefile `
    --console `
    --name Thanh_Dat_Phat_candidate `
    --distpath "$buildDistDir" `
    --workpath "$buildWorkDir" `
    --specpath "$buildSpecDir" `
    --version-file "$resolvedInputDir\version_info.txt" `
    --paths tdp_system `
    --hidden-import pdf_documents `
    --hidden-import excel_print_renderer `
    --hidden-import print_bundle `
    --hidden-import xcom_payment_documents `
    --hidden-import invoice_tax_export `
    --hidden-import outgoing_substitution `
    --hidden-import invoice_payment_scope `
    --hidden-import invoice_payment_documents `
    --hidden-import invoice_delivery_statement `
    --hidden-import invoice_input_export `
    --hidden-import invoice_input_sync `
    --hidden-import invoice_output_sync `
    --hidden-import invoice_workbench `
    --hidden-import invoice_workbench_listing `
    --hidden-import invoice_date_migration `
    --hidden-import physical_inventory `
    --hidden-import document_totals `
    --hidden-import round3_documents `
    --hidden-import document_preview `
    --hidden-import automatic_backup `
    --hidden-import round4_documents `
    --hidden-import minvoice_client `
    --hidden-import invoice_valuation `
    --hidden-import inventory_export `
    --hidden-import inventory_period_close `
    --hidden-import bk_import `
    --hidden-import pypdf `
    --hidden-import reportlab `
    --hidden-import reportlab.pdfbase._fontdata_widths_helvetica `
    --hidden-import reportlab.pdfbase._fontdata_widths_helveticabold `
    --hidden-import win32print `
    --hidden-import pythoncom `
    --hidden-import pywintypes `
    --hidden-import win32com.client `
    --add-data "$projectRoot\tdp_system\static;static" `
    --add-binary "$projectRoot\tdp_system\print_tools\SumatraPDF-3.6.1-64.exe;print_tools" `
    --add-data "$projectRoot\tdp_system\print_tools\SUMATRA_NOTICE.txt;print_tools" `
    --add-data "$projectRoot\demo_tdp\styles.css;shared" `
    --add-data "$projectRoot\tdp_system\templates;templates" `
    --add-data "$masterSource;." `
    --add-data "$openingTemplateSource;." `
    --add-data "$taxTemplateDir\thue 0.xlsx;tax_templates" `
    --add-data "$taxTemplateDir\thue 8.xlsx;tax_templates" `
    --add-data "$taxTemplateDir\thue 10.xlsx;tax_templates" `
    --add-data "$taxTemplateDir\thue 10 c$([char]0x00F3) khuy$([char]0x1EBF)n m$([char]0x1EA1)i.xlsx;tax_templates" `
    --add-data "$resolvedInputDir\connector.env;config" `
    --add-data "$resolvedInputDir\tdp_seed.sqlite3;seed" `
    tdp_system/server.py
  if ($LASTEXITCODE -ne 0) {
    throw "Build mot file EXE that bai"
  }

  $candidate = Join-Path $buildDistDir "Thanh_Dat_Phat_candidate.exe"
  if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
    throw "Khong tim thay EXE sau khi build"
  }
  $releaseDir = Join-Path $projectRoot "BAN_GIAO_TDP_MOT_FILE_20260905"
  if (-not [string]::IsNullOrWhiteSpace($env:TDP_RELEASE_DIR)) {
    $releaseDir = [IO.Path]::GetFullPath($env:TDP_RELEASE_DIR)
  }
  New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
  $releaseExe = Join-Path $releaseDir "Thanh_Dat_Phat.exe"
  if (Test-Path -LiteralPath $releaseExe -PathType Leaf) {
    $archiveDir = Join-Path $buildWorkRoot "dist\single_exe\archive"
    New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
    $archive = Join-Path $archiveDir ("Thanh_Dat_Phat_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".exe")
    Move-Item -LiteralPath $releaseExe -Destination $archive
  }
  Move-Item -LiteralPath $candidate -Destination $releaseExe
  $releaseFiles = @(Get-ChildItem -LiteralPath $releaseDir -File -Filter "*.exe")
  if ($releaseFiles.Count -ne 1 -or $releaseFiles[0].Name -ne "Thanh_Dat_Phat.exe") {
    throw "Thu muc ban giao khong dung mot file EXE duy nhat"
  }
  $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $releaseExe).Hash
  Write-Host "Da build file duy nhat: $releaseExe"
  Write-Host "SHA-256: $hash"
}
finally {
  if (Test-Path -LiteralPath $resolvedInputDir) {
    $deleteTarget = [IO.Path]::GetFullPath($resolvedInputDir)
    if ($deleteTarget.StartsWith($safeTempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $deleteTarget).StartsWith("tdp_single_exe_")) {
      Remove-Item -LiteralPath $deleteTarget -Recurse -Force
    }
  }
}
