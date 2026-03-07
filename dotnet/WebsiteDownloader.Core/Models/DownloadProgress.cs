namespace WebsiteDownloader.Core.Models;

/// <summary>
/// Reports download progress for a single file.
/// </summary>
public class DownloadProgress
{
    public string Url { get; set; } = string.Empty;
    public long BytesDownloaded { get; set; }
    public long TotalBytes { get; set; }
    public int Percentage { get; set; }

    /// <summary>Current download speed in KB/s.</summary>
    public double SpeedKbps { get; set; }

    /// <summary>Estimated time remaining.</summary>
    public TimeSpan EstimatedTimeRemaining { get; set; }

    /// <summary>Human-readable speed string.</summary>
    public string SpeedText { get; set; } = string.Empty;

    /// <summary>Human-readable ETA string.</summary>
    public string EtaText { get; set; } = string.Empty;
}
