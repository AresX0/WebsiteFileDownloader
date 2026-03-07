using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Input;
using WebsiteDownloader.Core.Models;
using WebsiteDownloader.Core.Services;

namespace WebsiteDownloader.UI.ViewModels;

/// <summary>
/// Main ViewModel for the Website Downloader application.
/// Manages scanning, download queue, hash-based dedup, config, history,
/// scheduling, Google Drive, speed tracking, pause/resume, and options.
/// </summary>
public class MainWindowViewModel : BindableBase, IDisposable
{
    private readonly WebsiteScanner _scanner;
    private readonly HashDatabase _hashDatabase;
    private FileDownloader _downloader;
    private CancellationTokenSource? _cancellationTokenSource;
    private FileLogger? _fileLogger;
    private readonly DownloadScheduler _scheduler;
    private readonly List<DownloadHistoryEntry> _history = [];
    private readonly List<string> _skippedFiles = [];
    private bool _disposed;

    private string _url = string.Empty;
    private string _outputDirectory = string.Empty;
    private bool _downloadImages = true;
    private bool _downloadVideos = true;
    private bool _downloadDocuments = true;
    private bool _downloadArchives = true;
    private bool _recursiveCrawl;
    private int _maxDepth = 1;
    private string? _urlPattern;
    private bool _followPagination = true;
    private int _maxPaginationPages = 100;
    private bool _useBrowserForScan;
    private bool _headlessBrowser = true;
    private int _maxConcurrentDownloads = 3;
    private int _requestDelayMs = 500;
    private bool _skipDuplicates = true;
    private bool _isScanning;
    private bool _isDownloading;
    private bool _isPaused;
    private int _progress;
    private string _statusMessage = string.Empty;
    private SiteProfile? _selectedProfile;
    private string _logText = string.Empty;
    private string _speedText = string.Empty;
    private string _etaText = string.Empty;
    private int _completedCount;
    private int _failedCount;
    private int _skippedCount;
    private string _historyText = string.Empty;
    private string _historyFilter = string.Empty;

    public MainWindowViewModel() : this(ConfigManager.Load()) { }

    public MainWindowViewModel(AppConfig config)
    {
        Config = config;
        _scheduler = new DownloadScheduler();
        _scheduler.ScheduleTriggered += () => OnScheduleTriggered();

        // Apply config values
        ApplyConfig();

        // Initialise core services (proxy aware)
        _scanner = new WebsiteScanner(config.ProxyUrl);
        _hashDatabase = new HashDatabase();
        _downloader = new FileDownloader(_hashDatabase);

        DownloadItems = new ObservableCollection<DownloadItemViewModel>();
        QueueUrls = new ObservableCollection<string>(config.QueueUrls);
        Profiles = new ObservableCollection<SiteProfile>(SiteProfile.GetBuiltInProfiles());

        // Init file logger
        if (!string.IsNullOrWhiteSpace(Config.LogDirectory))
        {
            try { _fileLogger = new FileLogger(Config.LogDirectory); }
            catch { /* non-fatal */ }
        }

        // Commands
        ScanCommand = new AsyncRelayCommand(ScanUrlAsync, () => !IsScanning && !string.IsNullOrWhiteSpace(Url));
        StartDownloadCommand = new AsyncRelayCommand(StartDownloadAsync, () => !IsDownloading && DownloadItems.Any(i => i.IsSelected));
        CancelCommand = new RelayCommand(_ => Cancel(), _ => IsScanning || IsDownloading);
        SelectAllCommand = new RelayCommand(_ => SelectAll());
        SelectNoneCommand = new RelayCommand(_ => SelectNone());
        BrowseOutputCommand = new RelayCommand(_ => BrowseOutput());
        ClearCommand = new RelayCommand(_ => Clear());
        ClearLogCommand = new RelayCommand(_ => LogText = string.Empty);

        // Restore schedule from config
        if (!string.IsNullOrEmpty(Config.ScheduleDays) && !string.IsNullOrEmpty(Config.ScheduleTime))
        {
            try
            {
                var days = new HashSet<DayOfWeek>();
                foreach (var d in Config.ScheduleDays.Split(',', StringSplitOptions.RemoveEmptyEntries))
                {
                    if (Enum.TryParse<DayOfWeek>(d.Trim(), out var day)) days.Add(day);
                }
                if (TimeOnly.TryParse(Config.ScheduleTime, out var time) && days.Count > 0)
                {
                    _scheduler.SetSchedule(new ScheduleEntry { Days = days, Time = time });
                }
            }
            catch { /* ignore bad config */ }
        }
    }

    #region Properties

    public AppConfig Config { get; }
    public DownloadScheduler Scheduler => _scheduler;

    public string Url
    {
        get => _url;
        set
        {
            if (SetProperty(ref _url, value))
                RaiseCommandsCanExecuteChanged();
        }
    }

    public string OutputDirectory
    {
        get => _outputDirectory;
        set => SetProperty(ref _outputDirectory, value);
    }

    public bool DownloadImages { get => _downloadImages; set => SetProperty(ref _downloadImages, value); }
    public bool DownloadVideos { get => _downloadVideos; set => SetProperty(ref _downloadVideos, value); }
    public bool DownloadDocuments { get => _downloadDocuments; set => SetProperty(ref _downloadDocuments, value); }
    public bool DownloadArchives { get => _downloadArchives; set => SetProperty(ref _downloadArchives, value); }
    public bool RecursiveCrawl { get => _recursiveCrawl; set => SetProperty(ref _recursiveCrawl, value); }
    public int MaxDepth { get => _maxDepth; set => SetProperty(ref _maxDepth, value); }
    public string? UrlPattern { get => _urlPattern; set => SetProperty(ref _urlPattern, value); }
    public bool FollowPagination { get => _followPagination; set => SetProperty(ref _followPagination, value); }
    public int MaxPaginationPages { get => _maxPaginationPages; set => SetProperty(ref _maxPaginationPages, value); }
    public bool UseBrowserForScan { get => _useBrowserForScan; set => SetProperty(ref _useBrowserForScan, value); }
    public bool HeadlessBrowser { get => _headlessBrowser; set => SetProperty(ref _headlessBrowser, value); }
    public int MaxConcurrentDownloads { get => _maxConcurrentDownloads; set => SetProperty(ref _maxConcurrentDownloads, value); }
    public int RequestDelayMs { get => _requestDelayMs; set => SetProperty(ref _requestDelayMs, value); }
    public bool SkipDuplicates { get => _skipDuplicates; set => SetProperty(ref _skipDuplicates, value); }

    public bool IsScanning
    {
        get => _isScanning;
        set { if (SetProperty(ref _isScanning, value)) RaiseCommandsCanExecuteChanged(); }
    }

    public bool IsDownloading
    {
        get => _isDownloading;
        set { if (SetProperty(ref _isDownloading, value)) RaiseCommandsCanExecuteChanged(); }
    }

    public bool IsPaused
    {
        get => _isPaused;
        set => SetProperty(ref _isPaused, value);
    }

    public int Progress { get => _progress; set => SetProperty(ref _progress, value); }
    public string StatusMessage { get => _statusMessage; set => SetProperty(ref _statusMessage, value); }
    public string LogText { get => _logText; set => SetProperty(ref _logText, value); }
    public string SpeedText { get => _speedText; set => SetProperty(ref _speedText, value); }
    public string EtaText { get => _etaText; set => SetProperty(ref _etaText, value); }
    public int CompletedCount { get => _completedCount; set => SetProperty(ref _completedCount, value); }
    public int FailedCount { get => _failedCount; set => SetProperty(ref _failedCount, value); }
    public int SkippedCount { get => _skippedCount; set => SetProperty(ref _skippedCount, value); }
    public string HistoryText { get => _historyText; set => SetProperty(ref _historyText, value); }
    public string HistoryFilter { get => _historyFilter; set { if (SetProperty(ref _historyFilter, value)) RefreshHistory(); } }

    public SiteProfile? SelectedProfile
    {
        get => _selectedProfile;
        set { if (SetProperty(ref _selectedProfile, value) && value != null) ApplyProfile(value); }
    }

    public ObservableCollection<DownloadItemViewModel> DownloadItems { get; }
    public ObservableCollection<string> QueueUrls { get; }
    public ObservableCollection<SiteProfile> Profiles { get; }

    #endregion

    #region Commands

    public ICommand ScanCommand { get; }
    public ICommand StartDownloadCommand { get; }
    public ICommand CancelCommand { get; }
    public ICommand SelectAllCommand { get; }
    public ICommand SelectNoneCommand { get; }
    public ICommand BrowseOutputCommand { get; }
    public ICommand ClearCommand { get; }
    public ICommand ClearLogCommand { get; }

    #endregion

    #region Config

    /// <summary>Apply config values to VM properties.</summary>
    public void ApplyConfig()
    {
        OutputDirectory = string.IsNullOrWhiteSpace(Config.OutputDirectory)
            ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "Website Downloads")
            : Config.OutputDirectory;
        MaxConcurrentDownloads = Config.MaxConcurrentDownloads;
        RequestDelayMs = Config.RequestDelayMs;
        SkipDuplicates = Config.SkipDuplicates;
        FollowPagination = Config.FollowPagination;
        MaxPaginationPages = Config.MaxPaginationPages;
        RecursiveCrawl = Config.RecursiveCrawl;
        MaxDepth = Config.MaxDepth;
        UseBrowserForScan = Config.UseBrowserForScan;
        HeadlessBrowser = Config.HeadlessBrowser;
        DownloadDocuments = Config.DownloadDocuments;
        DownloadImages = Config.DownloadImages;
        DownloadVideos = Config.DownloadVideos;
        DownloadArchives = Config.DownloadArchives;
    }

    /// <summary>Save current VM state back to config + disk.</summary>
    public void SaveConfig()
    {
        Config.OutputDirectory = OutputDirectory;
        Config.MaxConcurrentDownloads = MaxConcurrentDownloads;
        Config.RequestDelayMs = RequestDelayMs;
        Config.SkipDuplicates = SkipDuplicates;
        Config.FollowPagination = FollowPagination;
        Config.MaxPaginationPages = MaxPaginationPages;
        Config.RecursiveCrawl = RecursiveCrawl;
        Config.MaxDepth = MaxDepth;
        Config.UseBrowserForScan = UseBrowserForScan;
        Config.HeadlessBrowser = HeadlessBrowser;
        Config.DownloadDocuments = DownloadDocuments;
        Config.DownloadImages = DownloadImages;
        Config.DownloadVideos = DownloadVideos;
        Config.DownloadArchives = DownloadArchives;
        Config.QueueUrls = [.. QueueUrls];
        ConfigManager.Save(Config);
    }

    #endregion

    #region Profile

    public void ApplyProfile(SiteProfile profile)
    {
        Url = profile.Url;
        DownloadImages = profile.Options.DownloadImages;
        DownloadVideos = profile.Options.DownloadVideos;
        DownloadDocuments = profile.Options.DownloadDocuments;
        DownloadArchives = profile.Options.DownloadArchives;
        RecursiveCrawl = profile.Options.RecursiveCrawl;
        MaxDepth = profile.Options.MaxDepth;
        UrlPattern = profile.Options.UrlPattern;
        FollowPagination = profile.Options.FollowPagination;
        MaxPaginationPages = profile.Options.MaxPaginationPages;
        MaxConcurrentDownloads = profile.Options.MaxConcurrentDownloads;
        RequestDelayMs = profile.Options.RequestDelayMs;
        UseBrowserForScan = profile.Options.UseBrowserForScan;
        HeadlessBrowser = profile.Options.HeadlessBrowser;

        AppendLog($"Loaded profile: {profile.Name}");
        if (profile.AdditionalUrls.Count > 0)
            AppendLog($"  {profile.AdditionalUrls.Count} sub-URLs will be scanned");
    }

    #endregion

    #region Scan

    public async Task ScanUrlAsync()
    {
        if (string.IsNullOrWhiteSpace(Url)) return;

        IsScanning = true;
        DownloadItems.Clear();
        ResetCounters();
        StatusMessage = "Scanning website...";
        Progress = 0;
        _cancellationTokenSource = new CancellationTokenSource();

        try
        {
            var options = BuildOptions();
            var scanProgress = new Progress<ScanProgress>(p =>
            {
                StatusMessage = p.Message;
                AppendLog($"[Scan] {p.Message}");
            });

            List<DownloadItem> items;

            if (_selectedProfile?.AdditionalUrls.Count > 0)
            {
                AppendLog($"Scanning {_selectedProfile.AdditionalUrls.Count} data set URLs...");
                items = await Task.Run(() =>
                    _scanner.ScanMultipleAsync(
                        _selectedProfile.AdditionalUrls, options, scanProgress, _cancellationTokenSource.Token),
                    _cancellationTokenSource.Token);
            }
            else
            {
                items = await Task.Run(() =>
                    _scanner.ScanAsync(Url, options, scanProgress, _cancellationTokenSource.Token),
                    _cancellationTokenSource.Token);
            }

            // Batch add
            const int batchSize = 100;
            for (int i = 0; i < items.Count; i += batchSize)
            {
                foreach (var item in items.Skip(i).Take(batchSize))
                    DownloadItems.Add(new DownloadItemViewModel(item));
                if (i + batchSize < items.Count) await Task.Delay(10);
            }

            StatusMessage = $"Found {DownloadItems.Count} files";
            AppendLog($"Scan complete: {DownloadItems.Count} files found");
        }
        catch (OperationCanceledException)
        {
            StatusMessage = "Scan cancelled";
            AppendLog("Scan cancelled by user");
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error: {ex.Message}";
            AppendLog($"[Error] {ex.Message}");
            _fileLogger?.Log("ERROR", $"Scan error: {ex}");
        }
        finally
        {
            IsScanning = false;
            _cancellationTokenSource?.Dispose();
            _cancellationTokenSource = null;
        }
    }

    #endregion

    #region Download

    public async Task StartDownloadAsync()
    {
        if (string.IsNullOrWhiteSpace(OutputDirectory))
        {
            StatusMessage = "Please select an output directory";
            return;
        }

        if (!Directory.Exists(OutputDirectory))
        {
            try { Directory.CreateDirectory(OutputDirectory); }
            catch (Exception ex) { StatusMessage = $"Error creating directory: {ex.Message}"; return; }
        }

        // Rebuild downloader with current config
        var opts = BuildOptions();
        _downloader = new FileDownloader(_hashDatabase);

        IsDownloading = true;
        IsPaused = false;
        Progress = 0;
        ResetCounters();
        _cancellationTokenSource = new CancellationTokenSource();

        var selectedItems = DownloadItems.Where(i => i.IsSelected).ToList();
        var completed = 0;
        var failed = 0;
        var skippedDupes = 0;
        var total = selectedItems.Count;
        var overallTracker = new SpeedTracker();

        try
        {
            // Pre-scan for hash dedup
            if (SkipDuplicates)
            {
                AppendLog("Scanning existing files for duplicates...");
                StatusMessage = "Scanning existing files for duplicates...";
                var hashProgress = new Progress<(int scanned, int total, string currentFile)>(p =>
                    StatusMessage = $"Hashing existing files: {p.scanned}/{p.total} — {p.currentFile}");
                await Task.Run(() =>
                    _hashDatabase.ScanExistingFilesAsync(OutputDirectory, hashProgress, _cancellationTokenSource.Token),
                    _cancellationTokenSource.Token);
                AppendLog($"Hash database loaded: {_hashDatabase.Count} known files");
            }

            AppendLog($"Starting download of {total} files to {OutputDirectory}");
            _fileLogger?.Log("INFO", $"Download started: {total} files to {OutputDirectory}");
            overallTracker.Start(0);

            using var semaphore = new SemaphoreSlim(MaxConcurrentDownloads);
            var dispatcher = Application.Current.Dispatcher;

            var tasks = selectedItems.Select(async item =>
            {
                await semaphore.WaitAsync(_cancellationTokenSource.Token);
                var sw = Stopwatch.StartNew();
                try
                {
                    dispatcher.Invoke(() => item.Status = "Downloading");

                    var progress = new Progress<DownloadProgress>(p =>
                    {
                        dispatcher.Invoke(() =>
                        {
                            item.Progress = p.Percentage;
                            overallTracker.Update(p.BytesDownloaded);
                            SpeedText = overallTracker.SpeedText;
                        });
                    });

                    var result = await _downloader.DownloadWithRetryAsync(
                        item.Item, OutputDirectory, 3, SkipDuplicates, progress, _cancellationTokenSource.Token);

                    sw.Stop();
                    var entry = new DownloadHistoryEntry
                    {
                        Url = item.Url,
                        FileName = item.FileName,
                        BytesDownloaded = result.BytesDownloaded,
                        Hash = result.Hash,
                        Duration = sw.Elapsed
                    };

                    if (result.SkippedDuplicate)
                    {
                        dispatcher.Invoke(() => { item.Status = "Skipped (duplicate)"; item.Progress = 100; });
                        Interlocked.Increment(ref skippedDupes);
                        Interlocked.Increment(ref completed);
                        entry.Status = "Skipped";
                        lock (_skippedFiles) _skippedFiles.Add(item.FileName);
                    }
                    else if (result.Success)
                    {
                        dispatcher.Invoke(() => { item.Status = "Completed"; item.Progress = 100; });
                        Interlocked.Increment(ref completed);
                        entry.Status = "Completed";
                        entry.SpeedKbps = sw.Elapsed.TotalSeconds > 0 ? result.BytesDownloaded / 1024.0 / sw.Elapsed.TotalSeconds : 0;
                    }
                    else
                    {
                        dispatcher.Invoke(() => { item.Status = "Failed"; item.ErrorMessage = result.ErrorMessage; });
                        Interlocked.Increment(ref failed);
                        entry.Status = "Failed";
                        entry.ErrorMessage = result.ErrorMessage;
                        AppendLog($"[Failed] {item.FileName}: {result.ErrorMessage}");
                        _fileLogger?.Log("ERROR", $"Download failed: {item.FileName} — {result.ErrorMessage}");
                    }

                    lock (_history) _history.Add(entry);

                    var done = Interlocked.Add(ref completed, 0) + Interlocked.Add(ref failed, 0);
                    var pct = total > 0 ? (done * 100) / total : 0;
                    var dupes = Interlocked.Add(ref skippedDupes, 0);

                    dispatcher.Invoke(() =>
                    {
                        Progress = pct;
                        CompletedCount = Interlocked.Add(ref completed, 0);
                        FailedCount = Interlocked.Add(ref failed, 0);
                        SkippedCount = dupes;
                        StatusMessage = $"Downloaded {completed}/{total} ({failed} failed, {dupes} dupes skipped)";
                        SpeedText = overallTracker.SpeedText;
                        if (total > 0 && done < total)
                        {
                            var remaining = total - done;
                            var avgMs = sw.Elapsed.TotalMilliseconds;
                            EtaText = remaining > 0 && avgMs > 0
                                ? $"~{TimeSpan.FromMilliseconds(avgMs * remaining / Math.Max(done, 1)):hh\\:mm\\:ss}"
                                : "";
                        }
                    });
                }
                finally
                {
                    semaphore.Release();
                }
            });

            await Task.WhenAll(tasks);

            var finalDupes = Interlocked.Add(ref skippedDupes, 0);
            StatusMessage = $"Complete: {completed} downloaded, {failed} failed, {finalDupes} duplicates skipped";
            AppendLog($"Download complete: {completed} ok, {failed} failed, {finalDupes} duplicates skipped");
            _fileLogger?.Log("INFO", $"Download complete: {completed} ok, {failed} failed, {finalDupes} dupes");
            SpeedText = string.Empty;
            EtaText = string.Empty;

            // Save queue state
            QueueManager.Save(new QueueState { Urls = [.. QueueUrls] });
        }
        catch (OperationCanceledException)
        {
            StatusMessage = "Download cancelled";
            AppendLog("Download cancelled by user");
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error: {ex.Message}";
            AppendLog($"[Error] {ex.Message}");
            _fileLogger?.Log("ERROR", $"Download error: {ex}");
        }
        finally
        {
            IsDownloading = false;
            IsPaused = false;
            _cancellationTokenSource?.Dispose();
            _cancellationTokenSource = null;
        }
    }

    #endregion

    #region Pause / Resume / Cancel

    public void Cancel()
    {
        _cancellationTokenSource?.Cancel();
        StatusMessage = "Cancelling...";
        AppendLog("Cancel requested");
    }

    public void Pause()
    {
        _downloader.Pause();
        IsPaused = true;
        StatusMessage = "Paused";
        AppendLog("Downloads paused");
    }

    public void Resume()
    {
        _downloader.Resume();
        IsPaused = false;
        StatusMessage = "Resumed";
        AppendLog("Downloads resumed");
    }

    #endregion

    #region URL Queue

    public void AddUrlToQueue(string url)
    {
        if (!QueueUrls.Contains(url))
        {
            QueueUrls.Add(url);
            AppendLog($"Added to queue: {url}");
        }
    }

    public void RemoveUrlFromQueue(int index)
    {
        if (index >= 0 && index < QueueUrls.Count)
            QueueUrls.RemoveAt(index);
    }

    public void MoveUrlInQueue(int index, int direction)
    {
        var newIndex = index + direction;
        if (newIndex < 0 || newIndex >= QueueUrls.Count) return;
        (QueueUrls[index], QueueUrls[newIndex]) = (QueueUrls[newIndex], QueueUrls[index]);
    }

    public void ClearQueue() => QueueUrls.Clear();

    #endregion

    #region Selection

    public void SelectAll()
    {
        foreach (var item in DownloadItems) item.IsSelected = true;
    }

    public void SelectNone()
    {
        foreach (var item in DownloadItems) item.IsSelected = false;
    }

    #endregion

    #region History

    public void RefreshHistory()
    {
        var sb = new StringBuilder();
        var filter = HistoryFilter?.Trim() ?? "";

        IEnumerable<DownloadHistoryEntry> entries;
        lock (_history) entries = _history.ToList();

        if (!string.IsNullOrEmpty(filter))
        {
            entries = entries.Where(e =>
                e.FileName.Contains(filter, StringComparison.OrdinalIgnoreCase) ||
                e.Url.Contains(filter, StringComparison.OrdinalIgnoreCase) ||
                e.Status.Contains(filter, StringComparison.OrdinalIgnoreCase));
        }

        foreach (var e in entries.OrderByDescending(e => e.Timestamp))
            sb.AppendLine(e.ToString());

        HistoryText = sb.ToString();
    }

    public void ClearHistory()
    {
        lock (_history) _history.Clear();
        HistoryText = string.Empty;
    }

    #endregion

    #region Test Link / Export / Skipped

    public async Task TestLinkAsync(string url)
    {
        StatusMessage = "Testing link...";
        var (reachable, message) = await _downloader.TestDownloadLinkAsync(url);
        if (reachable)
        {
            StatusMessage = $"Link OK — {message}";
            AppendLog($"Test link OK: {url} — {message}");
        }
        else
        {
            StatusMessage = $"Link failed — {message}";
            AppendLog($"Test link failed: {url} — {message}");
        }
    }

    public async Task ExportFileTreeAsync(string path)
    {
        if (!Directory.Exists(OutputDirectory))
        {
            StatusMessage = "Output directory does not exist.";
            return;
        }
        await Task.Run(() => FileDownloader.ExportFileTree(OutputDirectory, path));
        StatusMessage = $"File tree exported to {path}";
        AppendLog($"File tree exported to {path}");
    }

    public async Task RetryItemAsync(DownloadItemViewModel item)
    {
        if (string.IsNullOrWhiteSpace(OutputDirectory)) return;

        item.Status = "Downloading";
        item.Progress = 0;
        item.ErrorMessage = null;

        try
        {
            var progress = new Progress<DownloadProgress>(p => item.Progress = p.Percentage);
            var result = await _downloader.DownloadWithRetryAsync(
                item.Item, OutputDirectory, 3, SkipDuplicates, progress, CancellationToken.None);

            item.Status = result.Success ? "Completed" : "Failed";
            item.Progress = result.Success ? 100 : item.Progress;
            if (!result.Success) item.ErrorMessage = result.ErrorMessage;
        }
        catch (Exception ex)
        {
            item.Status = "Failed";
            item.ErrorMessage = ex.Message;
        }
    }

    public void ShowSkippedFiles()
    {
        string text;
        lock (_skippedFiles)
        {
            text = _skippedFiles.Count == 0
                ? "No files skipped in this session."
                : string.Join("\n", _skippedFiles);
        }
        MessageBox.Show(text, $"Skipped Files ({_skippedFiles.Count})", MessageBoxButton.OK, MessageBoxImage.Information);
    }

    #endregion

    #region Theme

    public void ToggleTheme()
    {
        Config.Theme = Config.Theme == "Dark" ? "Light" : "Dark";
        App.ApplyTheme(Config.Theme);
        AppendLog($"Theme changed to {Config.Theme}");
    }

    #endregion

    #region Browse / Utility

    public void BrowseOutput()
    {
        var dialog = new Microsoft.Win32.OpenFolderDialog
        {
            Title = "Select Output Directory",
            InitialDirectory = OutputDirectory
        };
        if (dialog.ShowDialog() == true)
            OutputDirectory = dialog.FolderName;
    }

    private void Clear()
    {
        DownloadItems.Clear();
        ResetCounters();
        StatusMessage = string.Empty;
        Progress = 0;
    }

    private void ResetCounters()
    {
        CompletedCount = 0;
        FailedCount = 0;
        SkippedCount = 0;
        SpeedText = string.Empty;
        EtaText = string.Empty;
    }

    #endregion

    #region Schedule

    private async void OnScheduleTriggered()
    {
        if (IsDownloading || IsScanning) return;

        AppendLog("Scheduled download triggered");
        _fileLogger?.Log("INFO", "Scheduled download triggered");

        // Auto-start: scan first URL in queue, then download
        var url = QueueUrls.FirstOrDefault() ?? Url;
        if (string.IsNullOrWhiteSpace(url)) return;

        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher == null) return;

        await dispatcher.InvokeAsync(async () =>
        {
            Url = url;
            await ScanUrlAsync();
            if (DownloadItems.Count > 0)
                await StartDownloadAsync();
        });
    }

    #endregion

    #region Internal

    private DownloadOptions BuildOptions() => new()
    {
        DownloadImages = DownloadImages,
        DownloadVideos = DownloadVideos,
        DownloadDocuments = DownloadDocuments,
        DownloadArchives = DownloadArchives,
        RecursiveCrawl = RecursiveCrawl,
        MaxDepth = MaxDepth,
        UrlPattern = UrlPattern,
        FollowPagination = FollowPagination,
        MaxPaginationPages = MaxPaginationPages,
        MaxConcurrentDownloads = MaxConcurrentDownloads,
        RequestDelayMs = RequestDelayMs,
        UseBrowserForScan = UseBrowserForScan,
        HeadlessBrowser = HeadlessBrowser,
        SkipDuplicates = SkipDuplicates,
        ProxyUrl = Config.ProxyUrl,
        SpeedLimitKbps = Config.SpeedLimitKbps,
        MirrorDirectoryStructure = Config.MirrorDirectoryStructure,
    };

    private void AppendLog(string message)
    {
        var timestamp = DateTime.Now.ToString("HH:mm:ss");
        var line = $"[{timestamp}] {message}";
        LogText += line + "\n";
        _fileLogger?.Log("INFO", message);
    }

    private void RaiseCommandsCanExecuteChanged()
    {
        (ScanCommand as AsyncRelayCommand)?.RaiseCanExecuteChanged();
        (StartDownloadCommand as AsyncRelayCommand)?.RaiseCanExecuteChanged();
        (CancelCommand as RelayCommand)?.RaiseCanExecuteChanged();
    }

    /// <summary>Save config and dispose resources. Called on window close.</summary>
    public void SaveAndDispose()
    {
        SaveConfig();
        Dispose();
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _scheduler.Dispose();
        _fileLogger?.Dispose();
        GC.SuppressFinalize(this);
    }

    #endregion
}
