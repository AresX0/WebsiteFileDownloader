using System.Diagnostics;
using System.Net;
using HtmlAgilityPack;
using WebsiteDownloader.Core.Models;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// Scans websites for downloadable files. Supports:
/// - HTML parsing with HtmlAgilityPack (fast, no browser)
/// - Playwright browser automation (for JS-rendered sites, CAPTCHA handling)
/// - Full pagination following across all pages
/// - Recursive crawl with depth control
/// - File type filtering (images, videos, documents, archives)
/// </summary>
public class WebsiteScanner : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly HttpClientHandler _httpHandler;
    private bool _disposed;
    private bool _playwrightInstalled;
    private readonly SemaphoreSlim _installLock = new(1, 1);

    private static readonly HashSet<string> ImageExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff", ".tif"
    };

    private static readonly HashSet<string> VideoExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"
    };

    private static readonly HashSet<string> DocumentExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv",
        ".rtf", ".odt", ".ods", ".odp", ".epub"
    };

    private static readonly HashSet<string> ArchiveExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tar.gz", ".tgz"
    };

    public WebsiteScanner(string? proxyUrl = null)
    {
        _httpHandler = new HttpClientHandler
        {
            AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate | DecompressionMethods.Brotli,
            AllowAutoRedirect = true,
            MaxAutomaticRedirections = 10,
            CookieContainer = new CookieContainer()
        };

        // Proxy support
        if (!string.IsNullOrWhiteSpace(proxyUrl))
        {
            _httpHandler.Proxy = new WebProxy(proxyUrl);
            _httpHandler.UseProxy = true;
        }

        _httpClient = new HttpClient(_httpHandler, disposeHandler: false)
        {
            Timeout = TimeSpan.FromSeconds(60)
        };

        // Browser-like headers to avoid WAF blocking
        _httpClient.DefaultRequestHeaders.Add("User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36");
        _httpClient.DefaultRequestHeaders.Add("Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8");
        _httpClient.DefaultRequestHeaders.Add("Accept-Language", "en-US,en;q=0.9");
        _httpClient.DefaultRequestHeaders.Add("Connection", "keep-alive");
        _httpClient.DefaultRequestHeaders.Add("Upgrade-Insecure-Requests", "1");
        _httpClient.DefaultRequestHeaders.Add("Sec-Fetch-Dest", "document");
        _httpClient.DefaultRequestHeaders.Add("Sec-Fetch-Mode", "navigate");
        _httpClient.DefaultRequestHeaders.Add("Sec-Fetch-Site", "none");
        _httpClient.DefaultRequestHeaders.Add("Sec-Fetch-User", "?1");
        _httpClient.DefaultRequestHeaders.Add("Cache-Control", "max-age=0");
    }

    /// <summary>
    /// Scans a URL (and its paginated pages) for downloadable files.
    /// </summary>
    public async Task<List<DownloadItem>> ScanAsync(
        string url,
        DownloadOptions options,
        IProgress<ScanProgress>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var items = new List<DownloadItem>();
        var visitedUrls = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        if (options.UseBrowserForScan)
        {
            await ScanWithBrowserAsync(url, url, items, visitedUrls, options, 0, progress, cancellationToken);
        }
        else
        {
            await ScanWithHttpAsync(url, url, items, visitedUrls, options, 0, progress, cancellationToken);
        }

        // Deduplicate by URL
        return items.DistinctBy(i => i.Url).ToList();
    }

    /// <summary>
    /// Scans multiple URLs (e.g., all data set pages for a site profile).
    /// </summary>
    public async Task<List<DownloadItem>> ScanMultipleAsync(
        IEnumerable<string> urls,
        DownloadOptions options,
        IProgress<ScanProgress>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var allItems = new List<DownloadItem>();

        foreach (var url in urls)
        {
            cancellationToken.ThrowIfCancellationRequested();

            progress?.Report(new ScanProgress
            {
                CurrentUrl = url,
                ItemsFound = allItems.Count,
                Message = $"Scanning {url}..."
            });

            var items = await ScanAsync(url, options, progress, cancellationToken);
            allItems.AddRange(items);

            if (options.RequestDelayMs > 0)
                await Task.Delay(options.RequestDelayMs, cancellationToken);
        }

        return allItems.DistinctBy(i => i.Url).ToList();
    }

    #region HTTP-based scanning

    private async Task ScanWithHttpAsync(
        string baseUrl, string currentUrl, List<DownloadItem> items,
        HashSet<string> visitedUrls, DownloadOptions options, int depth,
        IProgress<ScanProgress>? progress, CancellationToken cancellationToken)
    {
        if (visitedUrls.Contains(currentUrl))
            return;

        visitedUrls.Add(currentUrl);

        var pageNumber = PaginationHandler.GetPageNumber(currentUrl);

        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, currentUrl);
            if (depth > 0)
            {
                request.Headers.Add("Referer", baseUrl);
            }

            var response = await SendWithRetryAsync(request, options.MaxRetries, cancellationToken);
            if (response == null || !response.IsSuccessStatusCode)
            {
                Debug.WriteLine($"[Scan] HTTP {response?.StatusCode} for {currentUrl}");
                return;
            }

            var html = await response.Content.ReadAsStringAsync(cancellationToken);
            var doc = new HtmlDocument();
            doc.LoadHtml(html);

            // Extract downloadable file links
            ExtractDownloadItems(doc, baseUrl, items, options, pageNumber);

            progress?.Report(new ScanProgress
            {
                CurrentUrl = currentUrl,
                PagesScanned = visitedUrls.Count,
                ItemsFound = items.Count,
                Message = $"Page {pageNumber}: found {items.Count} items total"
            });

            // Follow pagination
            if (options.FollowPagination && pageNumber < options.MaxPaginationPages)
            {
                var nextPageUrl = PaginationHandler.FindNextPageUrl(doc, currentUrl);
                if (nextPageUrl != null && !visitedUrls.Contains(nextPageUrl))
                {
                    Debug.WriteLine($"[Pagination] Following: {nextPageUrl}");
                    if (options.RequestDelayMs > 0)
                        await Task.Delay(options.RequestDelayMs, cancellationToken);

                    await ScanWithHttpAsync(baseUrl, nextPageUrl, items, visitedUrls, options, depth + 1, progress, cancellationToken);
                }
            }

            // Recursive crawl of sub-links (not pagination, but navigation)
            if (options.RecursiveCrawl && depth < options.MaxDepth)
            {
                var subLinks = ExtractNavigationLinks(doc, baseUrl, currentUrl, visitedUrls);
                foreach (var link in subLinks.Take(options.MaxLinksPerPage))
                {
                    if (options.RequestDelayMs > 0)
                        await Task.Delay(options.RequestDelayMs, cancellationToken);

                    await ScanWithHttpAsync(baseUrl, link, items, visitedUrls, options, depth + 1, progress, cancellationToken);
                }
            }
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Scan] Error scanning {currentUrl}: {ex.Message}");
        }
    }

    #endregion

    #region Playwright browser-based scanning

    private async Task ScanWithBrowserAsync(
        string baseUrl, string currentUrl, List<DownloadItem> items,
        HashSet<string> visitedUrls, DownloadOptions options, int depth,
        IProgress<ScanProgress>? progress, CancellationToken cancellationToken)
    {
        if (visitedUrls.Contains(currentUrl))
            return;

        visitedUrls.Add(currentUrl);

        var pageNumber = PaginationHandler.GetPageNumber(currentUrl);

        try
        {
            // Install Playwright browsers once (thread-safe)
            await EnsurePlaywrightInstalledAsync(progress, cancellationToken).ConfigureAwait(false);

            using var playwright = await Microsoft.Playwright.Playwright.CreateAsync();
            await using var browser = await playwright.Chromium.LaunchAsync(new()
            {
                Headless = options.HeadlessBrowser
            });

            var context = await browser.NewContextAsync(new()
            {
                UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            });

            var page = await context.NewPageAsync();

            await ScanPageWithBrowserAsync(page, baseUrl, currentUrl, items, visitedUrls, options, depth, progress, cancellationToken);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Browser] Error: {ex.Message}. Falling back to HTTP scan.");
            progress?.Report(new ScanProgress
            {
                CurrentUrl = currentUrl,
                ItemsFound = items.Count,
                Message = $"Browser failed ({ex.Message}), falling back to HTTP..."
            });
            // Fallback to HTTP scanning
            visitedUrls.Remove(currentUrl);
            await ScanWithHttpAsync(baseUrl, currentUrl, items, visitedUrls, options, depth, progress, cancellationToken);
        }
    }

    /// <summary>
    /// Ensures Playwright Chromium browser is available. Thread-safe.
    /// First checks the default browser cache; only runs the install process if missing.
    /// </summary>
    private async Task EnsurePlaywrightInstalledAsync(
        IProgress<ScanProgress>? progress = null,
        CancellationToken cancellationToken = default)
    {
        if (_playwrightInstalled) return;

        await _installLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_playwrightInstalled) return;

            // Check if Chromium is already installed in the default Playwright cache
            var browserCacheDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "ms-playwright");

            if (Directory.Exists(browserCacheDir))
            {
                var chromiumDirs = Directory.GetDirectories(browserCacheDir, "chromium-*");
                foreach (var dir in chromiumDirs)
                {
                    if (File.Exists(Path.Combine(dir, "INSTALLATION_COMPLETE")))
                    {
                        progress?.Report(new ScanProgress
                        {
                            Message = $"Playwright Chromium already installed at {dir}"
                        });
                        _playwrightInstalled = true;
                        return;
                    }
                }
            }

            // Browser not found — need to install
            progress?.Report(new ScanProgress
            {
                Message = "Chromium browser not found. Installing (first-time setup, may take a few minutes)..."
            });

            var driverDir = Path.GetDirectoryName(typeof(Microsoft.Playwright.Playwright).Assembly.Location)!;
            var isWindows = System.Runtime.InteropServices.RuntimeInformation.IsOSPlatform(
                System.Runtime.InteropServices.OSPlatform.Windows);

            var psi = new System.Diagnostics.ProcessStartInfo
            {
                WorkingDirectory = driverDir,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };

            var ps1Path = Path.Combine(driverDir, "playwright.ps1");
            var cmdPath = Path.Combine(driverDir, "playwright.cmd");

            string commandDesc;
            if (File.Exists(ps1Path))
            {
                var pwsh = FindPowerShell();
                psi.FileName = pwsh;
                psi.Arguments = $"-NoProfile -ExecutionPolicy Bypass -File \"{ps1Path}\" install chromium";
                commandDesc = $"{pwsh} playwright.ps1 install chromium";
            }
            else if (File.Exists(cmdPath))
            {
                psi.FileName = isWindows ? "cmd.exe" : "/bin/sh";
                psi.Arguments = isWindows
                    ? $"/c \"\"{cmdPath}\" install chromium\""
                    : $"-c \"\\\"{cmdPath}\\\" install chromium\"";
                commandDesc = $"{cmdPath} install chromium";
            }
            else
            {
                progress?.Report(new ScanProgress
                {
                    Message = $"No playwright script at {driverDir}. Skipping install — will try to launch browser directly."
                });
                _playwrightInstalled = true; // Let Playwright.CreateAsync() fail with a clear error if needed
                return;
            }

            progress?.Report(new ScanProgress { Message = $"Running: {commandDesc}" });

            using var process = new System.Diagnostics.Process { StartInfo = psi };
            process.Start();
            progress?.Report(new ScanProgress { Message = $"Install process started (PID {process.Id})" });

            // Stream output to log
            _ = Task.Run(async () =>
            {
                try { string? l; while ((l = await process.StandardOutput.ReadLineAsync(CancellationToken.None)) != null)
                    progress?.Report(new ScanProgress { Message = $"[Playwright] {l}" }); } catch { }
            }, CancellationToken.None);
            _ = Task.Run(async () =>
            {
                try { string? l; while ((l = await process.StandardError.ReadLineAsync(CancellationToken.None)) != null)
                    progress?.Report(new ScanProgress { Message = $"[Playwright] {l}" }); } catch { }
            }, CancellationToken.None);

            using var cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            cts.CancelAfter(TimeSpan.FromMinutes(5));

            try
            {
                await process.WaitForExitAsync(cts.Token).ConfigureAwait(false);
                progress?.Report(new ScanProgress { Message = $"Install exited with code {process.ExitCode}" });
            }
            catch (OperationCanceledException)
            {
                try { process.Kill(entireProcessTree: true); } catch { }
                progress?.Report(new ScanProgress { Message = "Install timed out or cancelled. Will try browser anyway." });
            }

            _playwrightInstalled = true;
        }
        catch (OperationCanceledException) { throw; }
        catch (Exception ex)
        {
            progress?.Report(new ScanProgress { Message = $"Install error: {ex.Message}. Will try browser anyway." });
            _playwrightInstalled = true; // Let it try; Playwright.CreateAsync() will give a clear error
        }
        finally
        {
            _installLock.Release();
        }
    }

    /// <summary>
    /// Finds pwsh or powershell.exe, preferring pwsh (PowerShell Core).
    /// </summary>
    private static string FindPowerShell()
    {
        // Try pwsh first (PowerShell 7+)
        try
        {
            var psi = new System.Diagnostics.ProcessStartInfo("pwsh", "--version")
            {
                UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true
            };
            using var p = System.Diagnostics.Process.Start(psi);
            p?.WaitForExit(3000);
            if (p?.ExitCode == 0) return "pwsh";
        }
        catch { }

        // Fallback to Windows PowerShell
        return "powershell";
    }

    private async Task ScanPageWithBrowserAsync(
        Microsoft.Playwright.IPage page, string baseUrl, string currentUrl,
        List<DownloadItem> items, HashSet<string> visitedUrls, DownloadOptions options,
        int depth, IProgress<ScanProgress>? progress, CancellationToken cancellationToken)
    {
        if (visitedUrls.Contains(currentUrl))
            return;

        visitedUrls.Add(currentUrl);
        var pageNumber = PaginationHandler.GetPageNumber(currentUrl);

        try
        {
            var response = await page.GotoAsync(currentUrl, new() { WaitUntil = Microsoft.Playwright.WaitUntilState.NetworkIdle });

            // Solve CAPTCHA if needed (Akamai WAF "I am not a robot")
            await SolveCaptchaIfNeeded(page);

            var html = await page.ContentAsync();
            var doc = new HtmlDocument();
            doc.LoadHtml(html);

            ExtractDownloadItems(doc, baseUrl, items, options, pageNumber);

            progress?.Report(new ScanProgress
            {
                CurrentUrl = currentUrl,
                PagesScanned = visitedUrls.Count,
                ItemsFound = items.Count,
                Message = $"Page {pageNumber}: found {items.Count} items total"
            });

            // Follow pagination
            if (options.FollowPagination && pageNumber < options.MaxPaginationPages)
            {
                var nextPageUrl = PaginationHandler.FindNextPageUrl(doc, currentUrl);
                if (nextPageUrl != null && !visitedUrls.Contains(nextPageUrl))
                {
                    Debug.WriteLine($"[Browser Pagination] Following: {nextPageUrl}");
                    if (options.RequestDelayMs > 0)
                        await Task.Delay(options.RequestDelayMs, cancellationToken);

                    await ScanPageWithBrowserAsync(page, baseUrl, nextPageUrl, items, visitedUrls, options, depth + 1, progress, cancellationToken);
                }
            }

            // Recursive crawl
            if (options.RecursiveCrawl && depth < options.MaxDepth)
            {
                var subLinks = ExtractNavigationLinks(doc, baseUrl, currentUrl, visitedUrls);
                foreach (var link in subLinks.Take(options.MaxLinksPerPage))
                {
                    if (options.RequestDelayMs > 0)
                        await Task.Delay(options.RequestDelayMs, cancellationToken);

                    await ScanPageWithBrowserAsync(page, baseUrl, link, items, visitedUrls, options, depth + 1, progress, cancellationToken);
                }
            }
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Browser] Error on {currentUrl}: {ex.Message}");
        }
    }

    /// <summary>
    /// Detects and auto-clicks Akamai WAF "I am not a robot" CAPTCHA buttons.
    /// </summary>
    private static async Task SolveCaptchaIfNeeded(Microsoft.Playwright.IPage page, int maxAttempts = 3)
    {
        for (int attempt = 0; attempt < maxAttempts; attempt++)
        {
            var content = await page.ContentAsync();

            // Detect Akamai CAPTCHA patterns
            bool hasCaptcha = content.Contains("I am not a robot", StringComparison.OrdinalIgnoreCase) ||
                              content.Contains("Press and Hold", StringComparison.OrdinalIgnoreCase) ||
                              content.Contains("ak-challenge", StringComparison.OrdinalIgnoreCase) ||
                              content.Contains("_sec_challenge", StringComparison.OrdinalIgnoreCase);

            if (!hasCaptcha) return;

            Debug.WriteLine($"[CAPTCHA] Attempt {attempt + 1}: Solving CAPTCHA...");

            // Try common CAPTCHA button selectors
            string[] selectors =
            [
                "input.usa-button",
                "button[type='submit']",
                "input[type='submit']",
                "#challenge-form button",
                ".challenge-form button"
            ];

            bool clicked = false;
            foreach (var selector in selectors)
            {
                try
                {
                    var element = await page.QuerySelectorAsync(selector);
                    if (element != null && await element.IsVisibleAsync())
                    {
                        await element.ClickAsync();
                        clicked = true;
                        Debug.WriteLine($"[CAPTCHA] Clicked: {selector}");
                        break;
                    }
                }
                catch { /* try next selector */ }
            }

            if (clicked)
            {
                await page.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle);
                await Task.Delay(2000);
            }
            else
            {
                break; // No button found, give up
            }
        }
    }

    #endregion

    #region File extraction

    private void ExtractDownloadItems(HtmlDocument doc, string baseUrl, List<DownloadItem> items, DownloadOptions options, int pageNumber)
    {
        var allLinks = doc.DocumentNode.SelectNodes("//a[@href]");
        if (allLinks == null) return;

        foreach (var link in allLinks)
        {
            var href = link.GetAttributeValue("href", "");
            var fullUrl = UrlHelper.MakeAbsoluteUrl(baseUrl, href);
            if (string.IsNullOrEmpty(fullUrl)) continue;

            // Check URL pattern filter
            if (!IsMatchingPattern(fullUrl, options.UrlPattern)) continue;

            var ext = UrlHelper.GetCleanExtension(fullUrl);
            string? type = null;

            if (options.DownloadDocuments && DocumentExtensions.Contains(ext))
                type = "Document";
            else if (options.DownloadImages && ImageExtensions.Contains(ext))
                type = "Image";
            else if (options.DownloadVideos && VideoExtensions.Contains(ext))
                type = "Video";
            else if (options.DownloadArchives && ArchiveExtensions.Contains(ext))
                type = "Archive";

            if (type == null) continue;

            var cleanUrl = fullUrl.Split('?')[0];
            var fileName = Path.GetFileName(Uri.UnescapeDataString(new Uri(cleanUrl).AbsolutePath));

            if (string.IsNullOrWhiteSpace(fileName)) continue;

            items.Add(new DownloadItem
            {
                Url = fullUrl,
                FileName = fileName,
                Type = type,
                Status = "Pending",
                SourcePage = baseUrl,
                PageNumber = pageNumber
            });
        }

        // Also check images directly (img src)
        if (options.DownloadImages)
        {
            var imgNodes = doc.DocumentNode.SelectNodes("//img[@src]");
            if (imgNodes != null)
            {
                foreach (var img in imgNodes)
                {
                    var src = img.GetAttributeValue("src", "");
                    var fullUrl = UrlHelper.MakeAbsoluteUrl(baseUrl, src);
                    if (string.IsNullOrEmpty(fullUrl)) continue;
                    if (!IsMatchingPattern(fullUrl, options.UrlPattern)) continue;

                    var ext = UrlHelper.GetCleanExtension(fullUrl);
                    if (!ImageExtensions.Contains(ext)) continue;

                    var fileName = Path.GetFileName(Uri.UnescapeDataString(new Uri(fullUrl.Split('?')[0]).AbsolutePath));
                    if (string.IsNullOrWhiteSpace(fileName)) continue;

                    items.Add(new DownloadItem
                    {
                        Url = fullUrl,
                        FileName = fileName,
                        Type = "Image",
                        Status = "Pending",
                        SourcePage = baseUrl,
                        PageNumber = pageNumber
                    });
                }
            }
        }

        // Check video elements
        if (options.DownloadVideos)
        {
            var videoNodes = doc.DocumentNode.SelectNodes("//video[@src]|//video//source[@src]");
            if (videoNodes != null)
            {
                foreach (var video in videoNodes)
                {
                    var src = video.GetAttributeValue("src", "");
                    var fullUrl = UrlHelper.MakeAbsoluteUrl(baseUrl, src);
                    if (string.IsNullOrEmpty(fullUrl)) continue;
                    if (!IsMatchingPattern(fullUrl, options.UrlPattern)) continue;

                    var ext = UrlHelper.GetCleanExtension(fullUrl);
                    if (!VideoExtensions.Contains(ext)) continue;

                    var fileName = Path.GetFileName(Uri.UnescapeDataString(new Uri(fullUrl.Split('?')[0]).AbsolutePath));
                    if (string.IsNullOrWhiteSpace(fileName)) continue;

                    items.Add(new DownloadItem
                    {
                        Url = fullUrl,
                        FileName = fileName,
                        Type = "Video",
                        Status = "Pending",
                        SourcePage = baseUrl,
                        PageNumber = pageNumber
                    });
                }
            }
        }
    }

    private static List<string> ExtractNavigationLinks(HtmlDocument doc, string baseUrl, string currentUrl, HashSet<string> visitedUrls)
    {
        var links = new List<string>();
        var allLinks = doc.DocumentNode.SelectNodes("//a[@href]");
        if (allLinks == null) return links;

        var baseUri = new Uri(baseUrl);

        foreach (var link in allLinks)
        {
            var href = link.GetAttributeValue("href", "");
            var fullUrl = UrlHelper.MakeAbsoluteUrl(baseUrl, href);

            if (string.IsNullOrEmpty(fullUrl)) continue;
            if (visitedUrls.Contains(fullUrl)) continue;
            if (!Uri.TryCreate(fullUrl, UriKind.Absolute, out var targetUri)) continue;
            if (!targetUri.Host.Equals(baseUri.Host, StringComparison.OrdinalIgnoreCase)) continue;

            // Only follow links that share the base path
            if (targetUri.AbsolutePath.StartsWith(baseUri.AbsolutePath, StringComparison.OrdinalIgnoreCase))
            {
                // Skip file links (they have extensions)
                var ext = UrlHelper.GetCleanExtension(fullUrl);
                if (string.IsNullOrEmpty(ext) || ext == ".html" || ext == ".htm" || ext == ".php" || ext == ".asp" || ext == ".aspx")
                {
                    links.Add(fullUrl);
                }
            }
        }

        return links.Distinct().ToList();
    }

    #endregion

    #region Helpers

    private async Task<HttpResponseMessage?> SendWithRetryAsync(HttpRequestMessage request, int maxRetries, CancellationToken cancellationToken)
    {
        for (int attempt = 0; attempt <= maxRetries; attempt++)
        {
            try
            {
                // Clone request for retry (HttpRequestMessage can only be sent once)
                using var clone = new HttpRequestMessage(request.Method, request.RequestUri);
                foreach (var header in request.Headers)
                {
                    clone.Headers.TryAddWithoutValidation(header.Key, header.Value);
                }

                var response = await _httpClient.SendAsync(clone, cancellationToken);

                if (response.IsSuccessStatusCode)
                    return response;

                // Retry on rate limit (429) or server error (5xx)
                if ((int)response.StatusCode == 429 || (int)response.StatusCode >= 500)
                {
                    var delay = (int)Math.Pow(2, attempt) * 1000;
                    Debug.WriteLine($"[Retry] HTTP {response.StatusCode}, waiting {delay}ms (attempt {attempt + 1}/{maxRetries + 1})");
                    await Task.Delay(delay, cancellationToken);
                    continue;
                }

                // 403 Forbidden — likely WAF. Don't retry HTTP, needs browser
                if (response.StatusCode == HttpStatusCode.Forbidden)
                {
                    Debug.WriteLine($"[Scan] 403 Forbidden for {request.RequestUri} — may need browser mode");
                    return response;
                }

                return response;
            }
            catch (HttpRequestException) when (attempt < maxRetries)
            {
                var delay = (int)Math.Pow(2, attempt) * 1000;
                await Task.Delay(delay, cancellationToken);
            }
        }

        return null;
    }

    private static bool IsMatchingPattern(string url, string? pattern)
    {
        if (string.IsNullOrWhiteSpace(pattern))
            return true;

        try
        {
            return System.Text.RegularExpressions.Regex.IsMatch(url, pattern, System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        }
        catch
        {
            return url.Contains(pattern, StringComparison.OrdinalIgnoreCase);
        }
    }

    #endregion

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
                _installLock?.Dispose();
            }
            _disposed = true;
        }
    }
}
