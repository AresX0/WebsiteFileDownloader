using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using WebsiteDownloader.Core.Services;
using WebsiteDownloader.UI.ViewModels;
using WebsiteDownloader.UI.Views;

namespace WebsiteDownloader.UI;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
    }

    public MainWindow(MainWindowViewModel vm) : this()
    {
        DataContext = vm;
    }

    private MainWindowViewModel? ViewModel => DataContext as MainWindowViewModel;

    // ─── Scan / Download ───────────────────────────────────────────────

    private async void OnScanClick(object sender, RoutedEventArgs e)
    {
        if (ViewModel == null) return;
        ViewModel.Url = UrlTextBox.Text;

        if (string.IsNullOrWhiteSpace(ViewModel.Url))
        {
            MessageBox.Show("Please enter a website URL.", "Website Downloader",
                MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        await ViewModel.ScanUrlAsync();
    }

    private async void OnDownloadClick(object sender, RoutedEventArgs e)
    {
        if (ViewModel != null) await ViewModel.StartDownloadAsync();
    }

    private void OnCancelClick(object sender, RoutedEventArgs e) => ViewModel?.Cancel();
    private void OnPauseClick(object sender, RoutedEventArgs e) => ViewModel?.Pause();
    private void OnResumeClick(object sender, RoutedEventArgs e) => ViewModel?.Resume();
    private void OnSelectAllClick(object sender, RoutedEventArgs e) => ViewModel?.SelectAll();
    private void OnSelectNoneClick(object sender, RoutedEventArgs e) => ViewModel?.SelectNone();
    private void OnBrowseClick(object sender, RoutedEventArgs e) => ViewModel?.BrowseOutput();

    // ─── Log auto-scroll ───────────────────────────────────────────────

    private void OnLogTextChanged(object sender, TextChangedEventArgs e)
    {
        if (sender is TextBox tb)
            tb.ScrollToEnd();
    }

    // ─── URL Queue ─────────────────────────────────────────────────────

    private void OnAddUrlToQueue(object sender, RoutedEventArgs e)
    {
        if (ViewModel == null) return;
        var url = UrlTextBox.Text?.Trim();
        if (!string.IsNullOrWhiteSpace(url))
        {
            ViewModel.AddUrlToQueue(url);
            UrlTextBox.Text = string.Empty;
        }
    }

    private void OnQueueRemove(object sender, RoutedEventArgs e)
    {
        if (ViewModel == null || QueueListBox.SelectedIndex < 0) return;
        ViewModel.RemoveUrlFromQueue(QueueListBox.SelectedIndex);
    }

    private void OnQueueMoveUp(object sender, RoutedEventArgs e)
    {
        if (ViewModel == null || QueueListBox.SelectedIndex < 1) return;
        ViewModel.MoveUrlInQueue(QueueListBox.SelectedIndex, -1);
    }

    private void OnQueueMoveDown(object sender, RoutedEventArgs e)
    {
        if (ViewModel == null || QueueListBox.SelectedIndex < 0) return;
        ViewModel.MoveUrlInQueue(QueueListBox.SelectedIndex, 1);
    }

    private void OnQueueCopyUrl(object sender, RoutedEventArgs e)
    {
        if (QueueListBox.SelectedItem is string url)
            Clipboard.SetText(url);
    }

    private void OnQueueOpenInBrowser(object sender, RoutedEventArgs e)
    {
        if (QueueListBox.SelectedItem is string url)
            OpenUrl(url);
    }

    private void OnQueueClear(object sender, RoutedEventArgs e) => ViewModel?.ClearQueue();

    // ─── Test Link ─────────────────────────────────────────────────────

    private async void OnTestLinkClick(object sender, RoutedEventArgs e)
    {
        if (ViewModel == null) return;
        var url = UrlTextBox.Text?.Trim();
        if (string.IsNullOrWhiteSpace(url)) return;
        await ViewModel.TestLinkAsync(url);
    }

    // ─── DataGrid context menu ─────────────────────────────────────────

    private void OnCopyItemUrl(object sender, RoutedEventArgs e)
    {
        if (DownloadItemsDataGrid.SelectedItem is DownloadItemViewModel item)
            Clipboard.SetText(item.Url);
    }

    private void OnOpenItemInBrowser(object sender, RoutedEventArgs e)
    {
        if (DownloadItemsDataGrid.SelectedItem is DownloadItemViewModel item)
            OpenUrl(item.Url);
    }

    private async void OnRetryItem(object sender, RoutedEventArgs e)
    {
        if (ViewModel != null && DownloadItemsDataGrid.SelectedItem is DownloadItemViewModel item)
            await ViewModel.RetryItemAsync(item);
    }

    // ─── History ───────────────────────────────────────────────────────

    private void OnRefreshHistory(object sender, RoutedEventArgs e) => ViewModel?.RefreshHistory();
    private void OnClearHistory(object sender, RoutedEventArgs e) => ViewModel?.ClearHistory();

    // ─── Menu ──────────────────────────────────────────────────────────

    private void OnSettingsClick(object sender, RoutedEventArgs e)
    {
        if (ViewModel == null) return;
        var win = new SettingsWindow(ViewModel.Config) { Owner = this };
        if (win.ShowDialog() == true && win.Saved)
            ViewModel.ApplyConfig();
    }

    private void OnScheduleClick(object sender, RoutedEventArgs e)
    {
        if (ViewModel == null) return;
        var win = new ScheduleWindow(ViewModel.Scheduler) { Owner = this };
        win.ShowDialog();
    }

    private void OnOpenOutputFolderClick(object sender, RoutedEventArgs e)
    {
        if (ViewModel != null && Directory.Exists(ViewModel.OutputDirectory))
            Process.Start(new ProcessStartInfo(ViewModel.OutputDirectory) { UseShellExecute = true });
    }

    private void OnOpenLogFolderClick(object sender, RoutedEventArgs e)
    {
        var logDir = ViewModel?.Config.LogDirectory;
        if (!string.IsNullOrEmpty(logDir) && Directory.Exists(logDir))
            Process.Start(new ProcessStartInfo(logDir) { UseShellExecute = true });
    }

    private void OnExitClick(object sender, RoutedEventArgs e) => Close();

    private void OnToggleThemeClick(object sender, RoutedEventArgs e) => ViewModel?.ToggleTheme();

    private void OnViewSkippedClick(object sender, RoutedEventArgs e) => ViewModel?.ShowSkippedFiles();

    private async void OnExportFileTreeClick(object sender, RoutedEventArgs e)
    {
        if (ViewModel == null) return;
        var dialog = new Microsoft.Win32.SaveFileDialog
        {
            Title = "Export File Tree",
            Filter = "JSON files (*.json)|*.json",
            FileName = "file_tree.json"
        };
        if (dialog.ShowDialog() == true)
            await ViewModel.ExportFileTreeAsync(dialog.FileName);
    }

    private void OnAboutClick(object sender, RoutedEventArgs e)
    {
        var result = MessageBox.Show(
            $"Website File Downloader v{UpdateChecker.CurrentVersion}\n\n" +
            "A generic website file downloader with pagination,\n" +
            "SHA-256 dedup, proxy support, scheduling,\n" +
            "and Google Drive integration.\n\n" +
            "Built with .NET 10 + WPF.\n\n" +
            "Developed by Platysoft\n" +
            "https://PlatySoft.com",
            "About — Platysoft", MessageBoxButton.OKCancel, MessageBoxImage.Information);
        if (result == MessageBoxResult.Cancel)
            return;
        // If user clicks OK, open the Platysoft website
        try
        {
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
            {
                FileName = "https://PlatySoft.com",
                UseShellExecute = true
            });
        }
        catch { /* ignore if browser fails to open */ }
    }

    private async void OnCheckUpdatesClick(object sender, RoutedEventArgs e)
    {
        var newVersion = await UpdateChecker.CheckForUpdateAsync();
        if (newVersion != null)
        {
            var result = MessageBox.Show(
                $"A new version ({newVersion}) is available.\nYou are running: {UpdateChecker.CurrentVersion}\n\nDownload and install the update now?",
                "Update Available", MessageBoxButton.YesNo, MessageBoxImage.Information);
            if (result != MessageBoxResult.Yes)
                return;

            // Try to find and download the installer asset
            var asset = await UpdateChecker.GetInstallerAssetAsync();
            if (asset == null)
            {
                // Fallback: open releases page
                var fallback = MessageBox.Show(
                    "Could not find an installer in the latest release.\nOpen the releases page to download manually?",
                    "Update", MessageBoxButton.YesNo, MessageBoxImage.Warning);
                if (fallback == MessageBoxResult.Yes)
                    UpdateChecker.OpenReleasesPage();
                return;
            }

            try
            {
                // Simple progress via title bar
                var origTitle = Title;
                Title = $"Downloading update: {asset.Value.FileName}...";
                var progress = new Progress<double>(pct =>
                    Dispatcher.Invoke(() => Title = $"Downloading update: {pct:F0}%"));

                var installerPath = await UpdateChecker.DownloadInstallerAsync(
                    asset.Value.Url, asset.Value.FileName, progress);

                Title = "Launching installer...";
                UpdateChecker.LaunchInstaller(installerPath);

                // Shut down so the installer can overwrite files
                await Task.Delay(1500);
                Application.Current.Shutdown();
            }
            catch (Exception ex)
            {
                Title = "Website File Downloader";
                MessageBox.Show($"Update failed:\n{ex.Message}", "Update Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }
        else
        {
            MessageBox.Show($"You are running the latest version ({UpdateChecker.CurrentVersion}).", "Up to Date",
                MessageBoxButton.OK, MessageBoxImage.Information);
        }
    }

    private void OnReportIssueClick(object sender, RoutedEventArgs e) => UpdateChecker.OpenIssuePage();

    // ─── Drag and Drop ─────────────────────────────────────────────────

    private void OnDragOver(object sender, DragEventArgs e)
    {
        if (e.Data.GetDataPresent(DataFormats.FileDrop) || e.Data.GetDataPresent(DataFormats.Text))
        {
            e.Effects = DragDropEffects.Copy;
            e.Handled = true;
        }
    }

    private void OnDrop(object sender, DragEventArgs e)
    {
        if (ViewModel == null) return;

        // Files dropped (e.g., .txt with URLs)
        if (e.Data.GetDataPresent(DataFormats.FileDrop))
        {
            var files = e.Data.GetData(DataFormats.FileDrop) as string[];
            if (files != null)
            {
                foreach (var file in files)
                {
                    if (File.Exists(file) && Path.GetExtension(file).Equals(".txt", StringComparison.OrdinalIgnoreCase))
                    {
                        foreach (var line in File.ReadLines(file))
                        {
                            var trimmed = line.Trim();
                            if (Uri.TryCreate(trimmed, UriKind.Absolute, out _))
                                ViewModel.AddUrlToQueue(trimmed);
                        }
                    }
                }
            }
        }
        // Text dropped (URL)
        else if (e.Data.GetDataPresent(DataFormats.Text))
        {
            var text = e.Data.GetData(DataFormats.Text) as string;
            if (!string.IsNullOrWhiteSpace(text) && Uri.TryCreate(text.Trim(), UriKind.Absolute, out _))
                ViewModel.AddUrlToQueue(text.Trim());
        }
    }

    // ─── Keyboard ──────────────────────────────────────────────────────

    private void OnKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.F1)
        {
            OnAboutClick(sender, e);
            e.Handled = true;
        }
        else if (e.Key == Key.T && Keyboard.Modifiers == ModifierKeys.Control)
        {
            ViewModel?.ToggleTheme();
            e.Handled = true;
        }
    }

    // ─── Window lifecycle ──────────────────────────────────────────────

    private void OnWindowClosing(object sender, System.ComponentModel.CancelEventArgs e)
    {
        if (ViewModel == null) return;

        // Save window state
        ViewModel.Config.WindowWidth = ActualWidth;
        ViewModel.Config.WindowHeight = ActualHeight;
        ViewModel.Config.WindowLeft = Left;
        ViewModel.Config.WindowTop = Top;

        ViewModel.SaveAndDispose();
    }

    // ─── Helpers ───────────────────────────────────────────────────────

    private static void OpenUrl(string url)
    {
        try
        {
            Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
        }
        catch { }
    }
}
