using System.Diagnostics;
using System.Net;
using System.Security.Cryptography;
using WebsiteDownloader.Core.Models;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// Downloads files concurrently with progress reporting, retry logic,
/// SHA-256 hash-based duplicate detection, bandwidth throttling,
/// proxy support, hierarchical directory mirroring, and speed/ETA tracking.
/// </summary>
public class FileDownloader : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly HttpClientHandler _httpHandler;
    private readonly HashDatabase? _hashDatabase;
    private readonly ManualResetEventSlim _pauseEvent = new(true);
    private bool _disposed;

    /// <summary>Speed limit in KB/s (0 = unlimited).</summary>
    public int SpeedLimitKbps { get; set; }

    /// <summary>Mirror URL directory structure in output folder.</summary>
    public bool MirrorDirectoryStructure { get; set; } = true;

    /// <summary>True when downloads are paused.</summary>
    public bool IsPaused => !_pauseEvent.IsSet;

    public FileDownloader(HashDatabase? hashDatabase = null, string? proxyUrl = null)
    {
        _hashDatabase = hashDatabase;

        _httpHandler = new HttpClientHandler
        {
            AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate | DecompressionMethods.Brotli,
            AllowAutoRedirect = true,
            MaxAutomaticRedirections = 10
        };

        // Proxy support
        if (!string.IsNullOrWhiteSpace(proxyUrl))
        {
            _httpHandler.Proxy = new WebProxy(proxyUrl);
            _httpHandler.UseProxy = true;
            Debug.WriteLine($"[Download] Using proxy: {proxyUrl}");
        }

        _httpClient = new HttpClient(_httpHandler, disposeHandler: false)
        {
            Timeout = TimeSpan.FromMinutes(10)
        };

        _httpClient.DefaultRequestHeaders.Add("User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36");
        _httpClient.DefaultRequestHeaders.Add("Accept", "*/*");
        _httpClient.DefaultRequestHeaders.Add("Accept-Language", "en-US,en;q=0.9");
    }

    public void Pause() => _pauseEvent.Reset();
    public void Resume() => _pauseEvent.Set();

    /// <summary>
    /// Downloads a single file with progress reporting, speed tracking,
    /// bandwidth throttling, and optional hash-based dedup.
    /// </summary>
    public async Task<DownloadResult> DownloadFileAsync(
        DownloadItem item,
        string outputDirectory,
        bool skipDuplicates = true,
        IProgress<DownloadProgress>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var sw = Stopwatch.StartNew();
        try
        {
            var fileName = UrlHelper.SanitizeFileName(item.FileName);

            // Build output path — optionally mirror URL directory structure
            string subDir = string.Empty;
            if (MirrorDirectoryStructure && !string.IsNullOrEmpty(item.SourcePage))
            {
                subDir = GetMirrorSubDirectory(item.SourcePage);
            }

            var targetDir = string.IsNullOrEmpty(subDir)
                ? outputDirectory
                : Path.Combine(outputDirectory, subDir);

            if (!Directory.Exists(targetDir))
                Directory.CreateDirectory(targetDir);

            var relativePath = string.IsNullOrEmpty(subDir)
                ? fileName
                : Path.Combine(subDir, fileName);
            var filePath = Path.Combine(targetDir, fileName);

            // Pre-download dedup check
            if (File.Exists(filePath) && skipDuplicates && _hashDatabase != null)
            {
                var existingHash = HashDatabase.ComputeFileHash(filePath);
                if (existingHash != null && _hashDatabase.HashExists(existingHash))
                {
                    return new DownloadResult
                    {
                        Success = true, FilePath = filePath,
                        Hash = existingHash, SkippedDuplicate = true
                    };
                }
            }

            // Handle duplicate file names
            if (File.Exists(filePath))
            {
                var name = Path.GetFileNameWithoutExtension(fileName);
                var ext = Path.GetExtension(fileName);
                var counter = 1;
                while (File.Exists(filePath))
                {
                    fileName = $"{name}_{counter}{ext}";
                    filePath = Path.Combine(targetDir, fileName);
                    counter++;
                }
                relativePath = string.IsNullOrEmpty(subDir) ? fileName : Path.Combine(subDir, fileName);
            }

            using var response = await _httpClient.GetAsync(item.Url, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
            response.EnsureSuccessStatusCode();

            var totalBytes = response.Content.Headers.ContentLength ?? 0;
            var downloadedBytes = 0L;
            var speedTracker = new SpeedTracker();
            speedTracker.Start(totalBytes);

            var tempPath = filePath + ".tmp";
            var lastReport = DateTime.UtcNow;

            await using (var contentStream = await response.Content.ReadAsStreamAsync(cancellationToken))
            await using (var fileStream = new FileStream(tempPath, FileMode.Create, FileAccess.Write, FileShare.None, 81920, true))
            {
                var buffer = new byte[8192];
                int bytesRead;

                while ((bytesRead = await contentStream.ReadAsync(buffer, cancellationToken)) > 0)
                {
                    // Pause support
                    _pauseEvent.Wait(cancellationToken);

                    await fileStream.WriteAsync(buffer.AsMemory(0, bytesRead), cancellationToken);
                    downloadedBytes += bytesRead;

                    speedTracker.Update(downloadedBytes, totalBytes);

                    // Bandwidth throttling
                    if (SpeedLimitKbps > 0)
                    {
                        var targetBytesPerSec = SpeedLimitKbps * 1024.0;
                        var elapsed = speedTracker.Elapsed.TotalSeconds;
                        if (elapsed > 0)
                        {
                            var actualRate = downloadedBytes / elapsed;
                            if (actualRate > targetBytesPerSec)
                            {
                                var sleepMs = (int)((downloadedBytes / targetBytesPerSec - elapsed) * 1000);
                                if (sleepMs > 0)
                                    await Task.Delay(Math.Min(sleepMs, 1000), cancellationToken);
                            }
                        }
                    }

                    // Report progress at most every 200ms
                    var now = DateTime.UtcNow;
                    if ((now - lastReport).TotalMilliseconds >= 200 || downloadedBytes >= totalBytes)
                    {
                        lastReport = now;
                        progress?.Report(new DownloadProgress
                        {
                            Url = item.Url,
                            BytesDownloaded = downloadedBytes,
                            TotalBytes = totalBytes,
                            Percentage = totalBytes > 0 ? (int)((downloadedBytes * 100) / totalBytes) : 0,
                            SpeedKbps = speedTracker.SpeedKbps,
                            EstimatedTimeRemaining = speedTracker.EstimatedTimeRemaining,
                            SpeedText = speedTracker.SpeedText,
                            EtaText = speedTracker.EtaText
                        });
                    }
                }
            }

            speedTracker.Stop();

            // Compute hash
            var fileHash = HashDatabase.ComputeFileHash(tempPath);

            // Post-download dedup check
            if (skipDuplicates && _hashDatabase != null && fileHash != null && _hashDatabase.HashExists(fileHash))
            {
                try { File.Delete(tempPath); } catch { /* best effort */ }
                return new DownloadResult
                {
                    Success = true, FilePath = null,
                    BytesDownloaded = downloadedBytes, Hash = fileHash,
                    SkippedDuplicate = true
                };
            }

            File.Move(tempPath, filePath, overwrite: true);

            if (_hashDatabase != null && fileHash != null)
                _hashDatabase.RegisterFile(fileHash, relativePath);

            return new DownloadResult
            {
                Success = true, FilePath = filePath,
                BytesDownloaded = downloadedBytes, Hash = fileHash
            };
        }
        catch (Exception ex)
        {
            return new DownloadResult { Success = false, ErrorMessage = ex.Message };
        }
    }

    /// <summary>
    /// Downloads a file with retry logic and exponential backoff.
    /// </summary>
    public async Task<DownloadResult> DownloadWithRetryAsync(
        DownloadItem item,
        string outputDirectory,
        int maxRetries = 3,
        bool skipDuplicates = true,
        IProgress<DownloadProgress>? progress = null,
        CancellationToken cancellationToken = default)
    {
        DownloadResult? lastResult = null;

        for (int attempt = 0; attempt <= maxRetries; attempt++)
        {
            lastResult = await DownloadFileAsync(item, outputDirectory, skipDuplicates, progress, cancellationToken);
            if (lastResult.Success) return lastResult;

            if (attempt < maxRetries)
            {
                var delay = (int)Math.Pow(2, attempt) * 1000;
                Debug.WriteLine($"[Download Retry] {item.FileName} attempt {attempt + 1}/{maxRetries + 1}, waiting {delay}ms");
                await Task.Delay(delay, cancellationToken);
            }
        }

        return lastResult ?? new DownloadResult { Success = false, ErrorMessage = "Max retries exceeded" };
    }

    /// <summary>
    /// Tests if a download URL is reachable by sending a HEAD request.
    /// </summary>
    public async Task<(bool reachable, string message)> TestDownloadLinkAsync(string url, CancellationToken cancellationToken = default)
    {
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Head, url);
            using var response = await _httpClient.SendAsync(request, cancellationToken);
            var size = response.Content.Headers.ContentLength;
            var sizeStr = size.HasValue ? $" ({FormatSize(size.Value)})" : "";
            return (response.IsSuccessStatusCode,
                $"HTTP {(int)response.StatusCode} {response.StatusCode}{sizeStr}");
        }
        catch (Exception ex)
        {
            return (false, $"Error: {ex.Message}");
        }
    }

    /// <summary>
    /// Generates a JSON file tree of downloaded files.
    /// </summary>
    public static void ExportFileTree(string outputDirectory, string outputPath)
    {
        var tree = new Dictionary<string, List<string>>();

        if (Directory.Exists(outputDirectory))
        {
            foreach (var file in Directory.GetFiles(outputDirectory, "*", SearchOption.AllDirectories))
            {
                var dir = Path.GetDirectoryName(Path.GetRelativePath(outputDirectory, file)) ?? ".";
                if (!tree.ContainsKey(dir))
                    tree[dir] = [];
                tree[dir].Add(Path.GetFileName(file));
            }
        }

        var json = System.Text.Json.JsonSerializer.Serialize(tree,
            new System.Text.Json.JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(outputPath, json);
    }

    /// <summary>
    /// Builds a mirror sub-directory from a source URL path.
    /// E.g., https://www.justice.gov/epstein/doj-disclosures → epstein/doj-disclosures
    /// </summary>
    private static string GetMirrorSubDirectory(string sourceUrl)
    {
        try
        {
            var uri = new Uri(sourceUrl);
            var path = uri.AbsolutePath.Trim('/');
            // Sanitize path segments
            var segments = path.Split('/')
                .Where(s => !string.IsNullOrWhiteSpace(s))
                .Select(s => UrlHelper.SanitizeFileName(Uri.UnescapeDataString(s)));
            return Path.Combine(segments.ToArray());
        }
        catch
        {
            return string.Empty;
        }
    }

    private static string FormatSize(long bytes)
    {
        if (bytes < 1024) return $"{bytes} B";
        if (bytes < 1024 * 1024) return $"{bytes / 1024.0:F1} KB";
        if (bytes < 1024L * 1024 * 1024) return $"{bytes / (1024.0 * 1024):F1} MB";
        return $"{bytes / (1024.0 * 1024 * 1024):F1} GB";
    }

    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }

    protected virtual void Dispose(bool disposing)
    {
        if (!_disposed)
        {
            if (disposing)
            {
                _httpClient?.Dispose();
                _httpHandler?.Dispose();
                _pauseEvent?.Dispose();
            }
            _disposed = true;
        }
    }
}
