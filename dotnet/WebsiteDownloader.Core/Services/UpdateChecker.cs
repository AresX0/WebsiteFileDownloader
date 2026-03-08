using System.Diagnostics;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// Checks for application updates by fetching VERSION.txt from GitHub,
/// and can download + launch the installer from GitHub Releases.
/// </summary>
public static class UpdateChecker
{
    private const string GitHubRepo = "AresX0/WebsiteFileDownloader";
    private const string VersionUrl = $"https://raw.githubusercontent.com/{GitHubRepo}/main/VERSION.txt";
    private const string ReleasesApi = $"https://api.github.com/repos/{GitHubRepo}/releases/latest";
    public static string CurrentVersion => "2.1.1";

    /// <summary>
    /// Checks for a newer version. Returns the new version string if an update is available,
    /// or null if current version is up-to-date or the check fails.
    /// </summary>
    public static async Task<string?> CheckForUpdateAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
            client.DefaultRequestHeaders.UserAgent.ParseAdd("WebsiteFileDownloader/2.1.1");
            var remoteVersion = (await client.GetStringAsync(VersionUrl, cancellationToken)).Trim();

            if (!string.IsNullOrWhiteSpace(remoteVersion) &&
                !remoteVersion.Equals(CurrentVersion, StringComparison.OrdinalIgnoreCase))
            {
                Debug.WriteLine($"[Update] New version available: {remoteVersion} (current: {CurrentVersion})");
                return remoteVersion;
            }

            Debug.WriteLine("[Update] Up to date");
            return null;
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Update] Check failed: {ex.Message}");
            return null;
        }
    }

    /// <summary>
    /// Fetches the latest GitHub release and returns the download URL and filename
    /// of the first .msi or .exe installer asset found, or null if none.
    /// </summary>
    public static async Task<(string Url, string FileName)?> GetInstallerAssetAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };
            client.DefaultRequestHeaders.UserAgent.ParseAdd("WebsiteFileDownloader/2.1.1");
            client.DefaultRequestHeaders.Accept.ParseAdd("application/vnd.github+json");

            var json = await client.GetStringAsync(ReleasesApi, cancellationToken);
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;

            if (!root.TryGetProperty("assets", out var assets))
                return null;

            // Prefer MSI, fallback to EXE
            foreach (var ext in new[] { ".msi", ".exe" })
            {
                foreach (var asset in assets.EnumerateArray())
                {
                    var name = asset.GetProperty("name").GetString() ?? "";
                    if (name.EndsWith(ext, StringComparison.OrdinalIgnoreCase))
                    {
                        var url = asset.GetProperty("browser_download_url").GetString();
                        if (!string.IsNullOrEmpty(url))
                            return (url, name);
                    }
                }
            }
            return null;
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Update] Asset fetch failed: {ex.Message}");
            return null;
        }
    }

    /// <summary>
    /// Downloads the installer to a temp file and returns the path.
    /// </summary>
    public static async Task<string> DownloadInstallerAsync(string url, string fileName,
        IProgress<double>? progress = null, CancellationToken cancellationToken = default)
    {
        var destPath = Path.Combine(Path.GetTempPath(), fileName);

        using var client = new HttpClient { Timeout = TimeSpan.FromMinutes(10) };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("WebsiteFileDownloader/2.1.1");

        using var response = await client.GetAsync(url, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        response.EnsureSuccessStatusCode();
        var totalBytes = response.Content.Headers.ContentLength ?? -1;

        await using var contentStream = await response.Content.ReadAsStreamAsync(cancellationToken);
        await using var fileStream = new FileStream(destPath, FileMode.Create, FileAccess.Write, FileShare.None, 81920, true);

        var buffer = new byte[81920];
        long totalRead = 0;
        int bytesRead;
        while ((bytesRead = await contentStream.ReadAsync(buffer, cancellationToken)) > 0)
        {
            await fileStream.WriteAsync(buffer.AsMemory(0, bytesRead), cancellationToken);
            totalRead += bytesRead;
            if (totalBytes > 0)
                progress?.Report((double)totalRead / totalBytes * 100.0);
        }

        return destPath;
    }

    /// <summary>
    /// Launches the downloaded installer. For MSI files uses msiexec /i (upgrade in-place).
    /// </summary>
    public static void LaunchInstaller(string installerPath)
    {
        try
        {
            if (installerPath.EndsWith(".msi", StringComparison.OrdinalIgnoreCase))
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = "msiexec",
                    Arguments = $"/i \"{installerPath}\"",
                    UseShellExecute = true
                });
            }
            else
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = installerPath,
                    UseShellExecute = true
                });
            }
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Update] Failed to launch installer: {ex.Message}");
            throw;
        }
    }

    /// <summary>
    /// Opens the GitHub releases page in the default browser.
    /// </summary>
    public static void OpenReleasesPage()
    {
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = $"https://github.com/{GitHubRepo}/releases",
                UseShellExecute = true
            });
        }
        catch { /* best effort */ }
    }

    /// <summary>
    /// Opens the GitHub issues page for bug reports.
    /// </summary>
    public static void OpenIssuePage()
    {
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = $"https://github.com/{GitHubRepo}/issues/new",
                UseShellExecute = true
            });
        }
        catch { /* best effort */ }
    }
}
