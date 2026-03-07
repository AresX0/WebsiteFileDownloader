using System.Text.Json.Serialization;

namespace WebsiteDownloader.Core.Models;

/// <summary>
/// Application configuration persisted to config.json.
/// </summary>
public class AppConfig
{
    // General
    public string OutputDirectory { get; set; } = string.Empty;
    public string LogDirectory { get; set; } = string.Empty;
    public int MaxConcurrentDownloads { get; set; } = 3;
    public bool AutoStart { get; set; }
    public bool StartMinimized { get; set; }
    public bool SkipDuplicates { get; set; } = true;

    // Network
    public string? ProxyUrl { get; set; }
    public int SpeedLimitKbps { get; set; }
    public int RequestDelayMs { get; set; } = 500;

    // Appearance
    public string Theme { get; set; } = "Dark";

    // Browser
    public bool UseBrowserForScan { get; set; }
    public bool HeadlessBrowser { get; set; } = true;

    // File types
    public bool DownloadDocuments { get; set; } = true;
    public bool DownloadImages { get; set; } = true;
    public bool DownloadVideos { get; set; } = true;
    public bool DownloadArchives { get; set; } = true;

    // Crawl
    public bool FollowPagination { get; set; } = true;
    public int MaxPaginationPages { get; set; } = 100;
    public bool RecursiveCrawl { get; set; }
    public int MaxDepth { get; set; } = 1;
    public string? UrlPattern { get; set; }
    public bool MirrorDirectoryStructure { get; set; } = true;

    // Schedule
    public string? ScheduleDays { get; set; }
    public string? ScheduleTime { get; set; }

    // Queue
    public List<string> QueueUrls { get; set; } = [];
    public int ProcessedCount { get; set; }

    // Google Drive
    public string? GoogleCredentialsPath { get; set; }
    public bool UseGdownFallback { get; set; }

    // Window state
    public double WindowWidth { get; set; } = 1200;
    public double WindowHeight { get; set; } = 850;
    public double WindowLeft { get; set; } = double.NaN;
    public double WindowTop { get; set; } = double.NaN;
}
