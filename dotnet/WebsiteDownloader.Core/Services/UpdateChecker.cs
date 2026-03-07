using System.Diagnostics;
using System.Net.Http;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// Checks for application updates by fetching VERSION.txt from GitHub.
/// </summary>
public static class UpdateChecker
{
    private const string VersionUrl = "https://raw.githubusercontent.com/AresX0/WebsiteDownloader/main/VERSION.txt";
    public static string CurrentVersion => "1.0.0";

    /// <summary>
    /// Checks for a newer version. Returns the new version string if an update is available,
    /// or null if current version is up-to-date or the check fails.
    /// </summary>
    public static async Task<string?> CheckForUpdateAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
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
    /// Opens the GitHub releases page in the default browser.
    /// </summary>
    public static void OpenReleasesPage()
    {
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = "https://github.com/AresX0/WebsiteDownloader/releases",
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
                FileName = "https://github.com/AresX0/WebsiteDownloader/issues/new",
                UseShellExecute = true
            });
        }
        catch { /* best effort */ }
    }
}
