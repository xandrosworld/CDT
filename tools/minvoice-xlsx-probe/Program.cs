// Regression for the reported "Memory stream is not expandable" XLSX error.
// Usage: dotnet run --project tools/minvoice-xlsx-probe -- file.xlsx [...]
// This is a local compatibility check, not a substitute for portal import QA.
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;

if (args.Length == 0) return 2;
int failures = 0;
foreach (var file in args)
{
    try
    {
        using var stream = new MemoryStream(File.ReadAllBytes(file));
        using (var book = SpreadsheetDocument.Open(stream, true))
        {
            var part = book.WorkbookPart!;
            _ = part.Workbook.OuterXml;
            foreach (var sheet in part.WorksheetParts) _ = sheet.Worksheet.OuterXml;
            if (part.SharedStringTablePart is { } strings) _ = strings.SharedStringTable.OuterXml;
            if (part.WorkbookStylesPart is { } styles) _ = styles.Stylesheet.OuterXml;
            var errors = new OpenXmlValidator().Validate(book).Take(3).ToArray();
            if (errors.Length > 0)
                throw new InvalidDataException(string.Join("; ", errors.Select(e => e.Description)));
        } // Saving during Dispose must also fit the fixed-size stream.
        Console.WriteLine($"PASS {Path.GetFileName(file)}");
    }
    catch (Exception e)
    {
        failures++;
        Console.WriteLine($"FAIL {Path.GetFileName(file)}: {e.Message}");
    }
}
return failures == 0 ? 0 : 1;
