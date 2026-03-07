using System.IO;
using System.Windows;
using WebsiteDownloader.Core.Models;
using WebsiteDownloader.Core.Services;

namespace WebsiteDownloader.UI.Views;

public partial class SettingsWindow : Window
{
    private readonly AppConfig _config;

    public SettingsWindow(AppConfig config)
    {
        InitializeComponent();
        _config = config;
        LoadConfig();
    }

    /// <summary>True when the user clicked Save.</summary>
    public bool Saved { get; private set; }

    private void LoadConfig()
    {
        OutputDirBox.Text = _config.OutputDirectory;
        LogDirBox.Text = _config.LogDirectory;
        ConcurrentBox.Text = _config.MaxConcurrentDownloads.ToString();
        AutoStartCheck.IsChecked = _config.AutoStart;
        StartMinimizedCheck.IsChecked = _config.StartMinimized;
        MirrorDirsCheck.IsChecked = _config.MirrorDirectoryStructure;

        ProxyBox.Text = _config.ProxyUrl ?? string.Empty;
        SpeedLimitBox.Text = _config.SpeedLimitKbps.ToString();
        RequestDelayBox.Text = _config.RequestDelayMs.ToString();

        ThemeCombo.SelectedIndex = _config.Theme == "Light" ? 1 : 0;

        CredentialsBox.Text = _config.GoogleCredentialsPath ?? string.Empty;
        GdownFallbackCheck.IsChecked = _config.UseGdownFallback;
        SkipDuplicatesCheck.IsChecked = _config.SkipDuplicates;
    }

    private void ApplyToConfig()
    {
        _config.OutputDirectory = OutputDirBox.Text.Trim();
        _config.LogDirectory = LogDirBox.Text.Trim();

        if (int.TryParse(ConcurrentBox.Text, out var c) && c is >= 1 and <= 32)
            _config.MaxConcurrentDownloads = c;

        _config.AutoStart = AutoStartCheck.IsChecked == true;
        _config.StartMinimized = StartMinimizedCheck.IsChecked == true;
        _config.MirrorDirectoryStructure = MirrorDirsCheck.IsChecked == true;

        _config.ProxyUrl = string.IsNullOrWhiteSpace(ProxyBox.Text) ? null : ProxyBox.Text.Trim();
        if (int.TryParse(SpeedLimitBox.Text, out var sl) && sl >= 0) _config.SpeedLimitKbps = sl;
        if (int.TryParse(RequestDelayBox.Text, out var rd) && rd >= 0) _config.RequestDelayMs = rd;

        _config.Theme = ThemeCombo.SelectedIndex == 1 ? "Light" : "Dark";

        _config.GoogleCredentialsPath = string.IsNullOrWhiteSpace(CredentialsBox.Text) ? null : CredentialsBox.Text.Trim();
        _config.UseGdownFallback = GdownFallbackCheck.IsChecked == true;
        _config.SkipDuplicates = SkipDuplicatesCheck.IsChecked == true;
    }

    private void OnSave(object sender, RoutedEventArgs e)
    {
        ApplyToConfig();
        ConfigManager.Save(_config);
        Saved = true;
        DialogResult = true;
    }

    private void OnCancel(object sender, RoutedEventArgs e)
    {
        DialogResult = false;
    }

    private void OnBrowseOutputDir(object sender, RoutedEventArgs e)
    {
        var dialog = new Microsoft.Win32.OpenFolderDialog { Title = "Select Download Folder", InitialDirectory = OutputDirBox.Text };
        if (dialog.ShowDialog() == true) OutputDirBox.Text = dialog.FolderName;
    }

    private void OnBrowseLogDir(object sender, RoutedEventArgs e)
    {
        var dialog = new Microsoft.Win32.OpenFolderDialog { Title = "Select Log Folder", InitialDirectory = LogDirBox.Text };
        if (dialog.ShowDialog() == true) LogDirBox.Text = dialog.FolderName;
    }

    private void OnBrowseCredentials(object sender, RoutedEventArgs e)
    {
        var dialog = new Microsoft.Win32.OpenFileDialog
        {
            Title = "Select Google Credentials JSON",
            Filter = "JSON files (*.json)|*.json|All files (*.*)|*.*",
            InitialDirectory = string.IsNullOrEmpty(CredentialsBox.Text) ? "" : Path.GetDirectoryName(CredentialsBox.Text) ?? ""
        };
        if (dialog.ShowDialog() == true) CredentialsBox.Text = dialog.FileName;
    }

    private void OnExportSettings(object sender, RoutedEventArgs e)
    {
        ApplyToConfig();
        var dialog = new Microsoft.Win32.SaveFileDialog
        {
            Title = "Export Settings",
            Filter = "JSON files (*.json)|*.json",
            FileName = "website_downloader_settings.json"
        };
        if (dialog.ShowDialog() == true)
        {
            ConfigManager.Export(_config, dialog.FileName);
            MessageBox.Show("Settings exported.", "Export", MessageBoxButton.OK, MessageBoxImage.Information);
        }
    }

    private void OnImportSettings(object sender, RoutedEventArgs e)
    {
        var dialog = new Microsoft.Win32.OpenFileDialog
        {
            Title = "Import Settings",
            Filter = "JSON files (*.json)|*.json"
        };
        if (dialog.ShowDialog() == true)
        {
            var imported = ConfigManager.Import(dialog.FileName);
            if (imported != null)
            {
                // Copy imported values to the current config
                _config.OutputDirectory = imported.OutputDirectory;
                _config.LogDirectory = imported.LogDirectory;
                _config.MaxConcurrentDownloads = imported.MaxConcurrentDownloads;
                _config.AutoStart = imported.AutoStart;
                _config.StartMinimized = imported.StartMinimized;
                _config.ProxyUrl = imported.ProxyUrl;
                _config.SpeedLimitKbps = imported.SpeedLimitKbps;
                _config.RequestDelayMs = imported.RequestDelayMs;
                _config.Theme = imported.Theme;
                _config.GoogleCredentialsPath = imported.GoogleCredentialsPath;
                _config.UseGdownFallback = imported.UseGdownFallback;
                _config.SkipDuplicates = imported.SkipDuplicates;
                _config.MirrorDirectoryStructure = imported.MirrorDirectoryStructure;
                LoadConfig();
                MessageBox.Show("Settings imported.", "Import", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            else
            {
                MessageBox.Show("Failed to read settings file.", "Import Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }
    }

    private void OnRestoreDefaults(object sender, RoutedEventArgs e)
    {
        var result = MessageBox.Show("Reset all settings to defaults?", "Restore Defaults",
            MessageBoxButton.YesNo, MessageBoxImage.Question);
        if (result != MessageBoxResult.Yes) return;

        var defaults = ConfigManager.CreateDefault();
        _config.OutputDirectory = defaults.OutputDirectory;
        _config.LogDirectory = defaults.LogDirectory;
        _config.MaxConcurrentDownloads = defaults.MaxConcurrentDownloads;
        _config.AutoStart = defaults.AutoStart;
        _config.StartMinimized = defaults.StartMinimized;
        _config.ProxyUrl = defaults.ProxyUrl;
        _config.SpeedLimitKbps = defaults.SpeedLimitKbps;
        _config.RequestDelayMs = defaults.RequestDelayMs;
        _config.Theme = defaults.Theme;
        _config.GoogleCredentialsPath = defaults.GoogleCredentialsPath;
        _config.UseGdownFallback = defaults.UseGdownFallback;
        _config.SkipDuplicates = defaults.SkipDuplicates;
        _config.MirrorDirectoryStructure = defaults.MirrorDirectoryStructure;
        LoadConfig();
    }
}
