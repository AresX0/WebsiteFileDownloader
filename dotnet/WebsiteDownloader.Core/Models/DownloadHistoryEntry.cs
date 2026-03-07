namespace WebsiteDownloader.Core.Models;

/// <summary>
/// A single entry in the download history log.
/// </summary>
public class DownloadHistoryEntry
{
    public DateTime Timestamp { get; set; } = DateTime.Now;
    public string Url { get; set; } = string.Empty;
    public string FileName { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public long BytesDownloaded { get; set; }
    public string? Hash { get; set; }
    public string? ErrorMessage { get; set; }
    public double SpeedKbps { get; set; }
    public TimeSpan Duration { get; set; }

    public override string ToString() =>
        $"[{Timestamp:yyyy-MM-dd HH:mm:ss}] {Status,-12} {FileName} ({FormatSize(BytesDownloaded)}) [{SpeedKbps:F0} KB/s]" +
        (ErrorMessage != null ? $" — {ErrorMessage}" : "");

    private static string FormatSize(long bytes)
    {
        if (bytes < 1024) return $"{bytes} B";
        if (bytes < 1024 * 1024) return $"{bytes / 1024.0:F1} KB";
        if (bytes < 1024 * 1024 * 1024) return $"{bytes / (1024.0 * 1024):F1} MB";
        return $"{bytes / (1024.0 * 1024 * 1024):F1} GB";
    }
}

/// <summary>
/// Scheduled download definition.
/// </summary>
public class ScheduleEntry
{
    public HashSet<DayOfWeek> Days { get; set; } = [];
    public TimeOnly Time { get; set; }
    public DateTime? LastTriggered { get; set; }
}
