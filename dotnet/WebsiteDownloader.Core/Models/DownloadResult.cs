namespace WebsiteDownloader.Core.Models;

/// <summary>
/// Result of a single file download attempt.
/// </summary>
public class DownloadResult
{
    public bool Success { get; set; }
    public string? FilePath { get; set; }
    public long BytesDownloaded { get; set; }
    public string? ErrorMessage { get; set; }

    /// <summary>SHA-256 hash of the downloaded file (lowercase hex).</summary>
    public string? Hash { get; set; }

    /// <summary>True if the file was skipped because a duplicate hash already existed.</summary>
    public bool SkippedDuplicate { get; set; }
}
