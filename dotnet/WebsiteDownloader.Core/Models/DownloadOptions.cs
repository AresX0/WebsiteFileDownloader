namespace WebsiteDownloader.Core.Models;

/// <summary>
/// Options controlling website scanning and downloading behavior.
/// </summary>
public class DownloadOptions
{
    public bool DownloadImages { get; set; } = true;
    public bool DownloadVideos { get; set; } = true;
    public bool DownloadDocuments { get; set; } = true;
    public bool DownloadArchives { get; set; } = true;
    public bool RecursiveCrawl { get; set; } = false;
    public bool FollowPagination { get; set; } = true;
    public int MaxDepth { get; set; } = 1;
    public int MaxLinksPerPage { get; set; } = 50;
    public int MaxPaginationPages { get; set; } = 10000;
    public int MaxConcurrentDownloads { get; set; } = 3;
    public int RequestDelayMs { get; set; } = 500;
    public int MaxRetries { get; set; } = 3;
    public string? UrlPattern { get; set; }
    public bool UseBrowserForScan { get; set; } = false;
    public bool HeadlessBrowser { get; set; } = true;

    /// <summary>When true, computes SHA-256 hashes and skips already-downloaded files.</summary>
    public bool SkipDuplicates { get; set; } = true;

    /// <summary>HTTP/HTTPS proxy URL (e.g., http://user:pass@host:port).</summary>
    public string? ProxyUrl { get; set; }

    /// <summary>Download speed limit in KB/s (0 = unlimited).</summary>
    public int SpeedLimitKbps { get; set; }

    /// <summary>When true, mirrors the URL path structure in the output directory.</summary>
    public bool MirrorDirectoryStructure { get; set; } = true;
}
