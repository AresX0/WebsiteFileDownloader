namespace WebsiteDownloader.Core.Models;

/// <summary>
/// Scan progress report emitted during website scanning.
/// </summary>
public class ScanProgress
{
    public string CurrentUrl { get; set; } = string.Empty;
    public int PagesScanned { get; set; }
    public int ItemsFound { get; set; }
    public string Message { get; set; } = string.Empty;
}
