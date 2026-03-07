namespace WebsiteDownloader.Core.Models;

/// <summary>
/// Represents a single file discovered during website scanning.
/// </summary>
public class DownloadItem
{
    public string Url { get; set; } = string.Empty;
    public string FileName { get; set; } = string.Empty;
    public string Type { get; set; } = string.Empty;
    public string Status { get; set; } = "Pending";
    public long Size { get; set; }
    public int Progress { get; set; }
    public string? ErrorMessage { get; set; }
    public string? SourcePage { get; set; }
    public int PageNumber { get; set; }
}
