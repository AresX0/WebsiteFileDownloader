using System.Net;
using System.Text.RegularExpressions;
using HtmlAgilityPack;
using WebsiteDownloader.Core.Models;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// Detects and follows pagination on web pages.
/// Supports query-string (?page=N), aria-label, pager CSS class, and "Next" link patterns.
/// </summary>
public static class PaginationHandler
{
    /// <summary>
    /// Finds the "next page" URL from HTML pagination controls.
    /// Returns null if no next page is found.
    /// </summary>
    public static string? FindNextPageUrl(HtmlDocument doc, string currentUrl)
    {
        var currentUri = new Uri(currentUrl);
        var currentPageBase = currentUrl.Split('?')[0];

        var allLinks = doc.DocumentNode.SelectNodes("//a[@href]");
        if (allLinks == null) return null;

        foreach (var link in allLinks)
        {
            var href = link.GetAttributeValue("href", "");
            var ariaLabel = link.GetAttributeValue("aria-label", "");
            var linkClass = link.GetAttributeValue("class", "");
            var rel = link.GetAttributeValue("rel", "");
            var text = link.InnerText?.Trim() ?? "";

            if (string.IsNullOrWhiteSpace(href))
                continue;

            // Skip "Last page" links — we want sequential traversal
            if (ariaLabel.Equals("Last page", StringComparison.OrdinalIgnoreCase))
                continue;

            // Skip links that look like data set navigation, not pagination
            if (text.Contains("Data Set", StringComparison.OrdinalIgnoreCase) ||
                text.Contains("Dataset", StringComparison.OrdinalIgnoreCase))
                continue;

            bool isNextPage =
                // Aria labels
                ariaLabel.Equals("Next page", StringComparison.OrdinalIgnoreCase) ||
                ariaLabel.Equals("Go to next page", StringComparison.OrdinalIgnoreCase) ||
                // rel="next"
                rel.Equals("next", StringComparison.OrdinalIgnoreCase) ||
                // CSS classes (Drupal, Bootstrap, generic)
                linkClass.Contains("next-page", StringComparison.OrdinalIgnoreCase) ||
                linkClass.Contains("next_page", StringComparison.OrdinalIgnoreCase) ||
                linkClass.Contains("pager-next", StringComparison.OrdinalIgnoreCase) ||
                linkClass.Contains("pager__next", StringComparison.OrdinalIgnoreCase) ||
                linkClass.Contains("pagination-next", StringComparison.OrdinalIgnoreCase) ||
                // Text-based detection
                (text.Equals("Next", StringComparison.OrdinalIgnoreCase) && href.Contains("page=")) ||
                (text.Equals("Next ›", StringComparison.OrdinalIgnoreCase)) ||
                (text.Equals("›", StringComparison.OrdinalIgnoreCase) && href.Contains("page=")) ||
                (text.Equals("»", StringComparison.OrdinalIgnoreCase) && href.Contains("page=")) ||
                (text.Equals("Next →", StringComparison.OrdinalIgnoreCase));

            if (!isNextPage) continue;

            // Resolve to absolute URL
            string fullUrl;
            if (href.StartsWith('?'))
            {
                fullUrl = currentPageBase + href;
            }
            else
            {
                fullUrl = UrlHelper.MakeAbsoluteUrl(currentPageBase, href);
            }

            if (string.IsNullOrEmpty(fullUrl)) continue;
            if (!Uri.TryCreate(fullUrl, UriKind.Absolute, out var targetUri)) continue;
            if (!targetUri.Host.Equals(currentUri.Host, StringComparison.OrdinalIgnoreCase)) continue;

            return fullUrl;
        }

        return null;
    }

    /// <summary>
    /// Extracts the current page number from a URL with ?page=N query parameter.
    /// Returns 0 if no page parameter found.
    /// </summary>
    public static int GetPageNumber(string url)
    {
        var match = Regex.Match(url, @"[?&]page=(\d+)");
        return match.Success ? int.Parse(match.Groups[1].Value) : 0;
    }

    /// <summary>
    /// Detects whether a page has pagination controls.
    /// </summary>
    public static bool HasPagination(HtmlDocument doc)
    {
        // Check for common pagination container elements
        var pagerNodes = doc.DocumentNode.SelectNodes(
            "//nav[contains(@class,'pager')]|" +
            "//ul[contains(@class,'pagination')]|" +
            "//div[contains(@class,'pager')]|" +
            "//div[contains(@class,'pagination')]|" +
            "//nav[@aria-label='Pagination']");

        return pagerNodes != null && pagerNodes.Count > 0;
    }
}

/// <summary>
/// URL helper utilities.
/// </summary>
public static class UrlHelper
{
    public static string MakeAbsoluteUrl(string baseUrl, string relativeUrl)
    {
        if (string.IsNullOrWhiteSpace(relativeUrl))
            return string.Empty;

        if (Uri.IsWellFormedUriString(relativeUrl, UriKind.Absolute))
            return relativeUrl;

        if (Uri.TryCreate(new Uri(baseUrl), relativeUrl, out var absoluteUri))
            return absoluteUri.ToString();

        return string.Empty;
    }

    public static string SanitizeFileName(string fileName)
    {
        var decoded = WebUtility.UrlDecode(fileName);
        var invalid = Path.GetInvalidFileNameChars();
        foreach (var c in invalid)
        {
            decoded = decoded.Replace(c, '_');
        }
        return decoded;
    }

    /// <summary>
    /// Extracts the clean file extension from a URL (stripping query string).
    /// </summary>
    public static string GetCleanExtension(string url)
    {
        var cleanUrl = url.Split('?')[0].Split('#')[0];
        return Path.GetExtension(cleanUrl).ToLowerInvariant();
    }
}
