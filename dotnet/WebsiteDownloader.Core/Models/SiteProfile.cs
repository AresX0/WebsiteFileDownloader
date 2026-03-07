namespace WebsiteDownloader.Core.Models;

/// <summary>
/// A saved site profile for quick re-use (e.g., "DOJ Epstein Files").
/// </summary>
public class SiteProfile
{
    public string Name { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public string Url { get; set; } = string.Empty;
    public DownloadOptions Options { get; set; } = new();
    public List<string> AdditionalUrls { get; set; } = [];

    /// <summary>
    /// Built-in profiles for well-known data dump sites.
    /// </summary>
    public static List<SiteProfile> GetBuiltInProfiles() =>
    [
        new SiteProfile
        {
            Name = "DOJ Epstein Disclosures",
            Description = "All 12 data sets from the DOJ Epstein disclosures page with full pagination support",
            Url = "https://www.justice.gov/epstein/doj-disclosures",
            Options = new DownloadOptions
            {
                DownloadDocuments = true,
                DownloadImages = false,
                DownloadVideos = false,
                FollowPagination = true,
                MaxPaginationPages = 10000,
                RecursiveCrawl = true,
                MaxDepth = 2,
                RequestDelayMs = 1000,
                MaxConcurrentDownloads = 2,
                UseBrowserForScan = true,
            },
            AdditionalUrls =
            [
                "https://www.justice.gov/epstein/doj-disclosures/data-set-1-files",
                "https://www.justice.gov/epstein/doj-disclosures/data-set-2-files",
                "https://www.justice.gov/epstein/doj-disclosures/data-set-3-files",
                "https://www.justice.gov/epstein/doj-disclosures/data-set-4-files",
                "https://www.justice.gov/epstein/doj-disclosures/data-set-5-files",
                "https://www.justice.gov/epstein/doj-disclosures/data-set-6-files",
                "https://www.justice.gov/epstein/doj-disclosures/data-set-7-files",
                "https://www.justice.gov/epstein/doj-disclosures/data-set-8-files",
                "https://www.justice.gov/epstein/doj-disclosures/data-set-9-files",
                "https://www.justice.gov/epstein/doj-disclosures/data-set-10-files",
                "https://www.justice.gov/epstein/doj-disclosures/data-set-11-files",
                "https://www.justice.gov/epstein/doj-disclosures/data-set-12-files",
            ]
        },
        new SiteProfile
        {
            Name = "DOJ FOIA Reading Room",
            Description = "DOJ Freedom of Information Act Electronic Reading Room",
            Url = "https://www.justice.gov/oip/available-documents-foia-library",
            Options = new DownloadOptions
            {
                DownloadDocuments = true,
                FollowPagination = true,
                MaxPaginationPages = 500,
                RecursiveCrawl = true,
                MaxDepth = 2,
                RequestDelayMs = 1000,
            }
        },
        new SiteProfile
        {
            Name = "House Oversight (Custom URL)",
            Description = "Congressional documents from House Oversight committee",
            Url = "https://oversight.house.gov/release/",
            Options = new DownloadOptions
            {
                DownloadDocuments = true,
                FollowPagination = true,
                RecursiveCrawl = false,
                MaxPaginationPages = 100,
            }
        },
        new SiteProfile
        {
            Name = "Generic Website (enter URL)",
            Description = "Scan any website for downloadable files",
            Url = "",
            Options = new DownloadOptions
            {
                DownloadDocuments = true,
                DownloadImages = true,
                DownloadVideos = true,
                FollowPagination = true,
                MaxPaginationPages = 100,
                RecursiveCrawl = false,
                MaxDepth = 1,
            }
        }
    ];
}
