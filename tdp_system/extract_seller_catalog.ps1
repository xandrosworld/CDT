param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$targetPath = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $targetPath) { throw 'Destination already exists; choose a new file.' }
$excel = $null
$book = $null
$output = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.AutomationSecurity = 3
    $book = $excel.Workbooks.Open($sourcePath, 0, $true)
    $sheet = $book.Worksheets.Item('CCCD')
    $output = $excel.Workbooks.Add()
    $target = $output.Worksheets.Item(1)
    $target.Name = 'CCCD'
    # Values only: no macros, links, or financial-report sheets are copied.
    $target.Range('A1:F55').NumberFormat = '@'
    $targetRow = 1
    for ($row = 2; $row -le $sheet.UsedRange.Rows.Count; $row++) {
        # The source has a trailing empty-name formula row (#N/A), not a seller.
        if (-not ([string]$sheet.Cells.Item($row, 2).Text).Trim()) { continue }
        for ($col = 1; $col -le 6; $col++) {
            $target.Cells.Item($targetRow, $col).Value2 = [string]$sheet.Cells.Item($row, $col).Text
        }
        $targetRow++
    }
    $output.SaveAs($targetPath, 51)
    Write-Output 'Extracted CCCD reference sheet (values only).'
} finally {
    if ($output) { $output.Close($false) }
    if ($book) { $book.Close($false) }
    if ($excel) { $excel.Quit() }
    foreach ($item in @($target, $sheet, $output, $book, $excel)) {
        if ($item) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($item) }
    }
}
