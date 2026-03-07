using System.Windows;
using System.Windows.Media;
using Microsoft.Win32;
using WebsiteDownloader.Core.Models;
using WebsiteDownloader.Core.Services;
using WebsiteDownloader.UI.ViewModels;

namespace WebsiteDownloader.UI;

public partial class App : Application
{
    private SingleInstanceLock? _singleInstanceLock;

    private void OnAppStartup(object sender, StartupEventArgs e)
    {
        // Global exception handling
        DispatcherUnhandledException += (s, args) =>
        {
            MessageBox.Show(
                $"An unexpected error occurred:\n\n{args.Exception.Message}",
                "Website Downloader - Error",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
            args.Handled = true;
        };

        AppDomain.CurrentDomain.UnhandledException += (s, args) =>
        {
            if (args.ExceptionObject is Exception ex)
            {
                MessageBox.Show(
                    $"Fatal error:\n\n{ex.Message}",
                    "Website Downloader - Fatal Error",
                    MessageBoxButton.OK,
                    MessageBoxImage.Error);
            }
        };

        TaskScheduler.UnobservedTaskException += (s, args) => args.SetObserved();

        // Single instance lock
        _singleInstanceLock = new SingleInstanceLock();
        if (!_singleInstanceLock.TryAcquire())
        {
            MessageBox.Show("Website Downloader is already running.", "Single Instance",
                MessageBoxButton.OK, MessageBoxImage.Information);
            Shutdown();
            return;
        }

        // Load config
        var config = ConfigManager.Load();

        // Apply theme from config (or detect OS)
        var theme = config.Theme;
        if (string.IsNullOrEmpty(theme))
            theme = DetectOsTheme();
        ApplyTheme(theme);

        // Create VM
        var vm = new MainWindowViewModel(config);

        // Create and show window
        var mainWindow = new MainWindow(vm);

        // Restore window position/size
        if (!double.IsNaN(config.WindowLeft) && !double.IsNaN(config.WindowTop))
        {
            mainWindow.Left = config.WindowLeft;
            mainWindow.Top = config.WindowTop;
            mainWindow.WindowStartupLocation = WindowStartupLocation.Manual;
        }
        if (config.WindowWidth > 100) mainWindow.Width = config.WindowWidth;
        if (config.WindowHeight > 100) mainWindow.Height = config.WindowHeight;

        // Start minimized?
        if (config.StartMinimized)
            mainWindow.WindowState = WindowState.Minimized;

        mainWindow.Show();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _singleInstanceLock?.Dispose();
        base.OnExit(e);
    }

    /// <summary>Apply a Dark or Light theme by swapping brush colours.</summary>
    public static void ApplyTheme(string theme)
    {
        var res = Current.Resources;
        if (theme == "Light")
        {
            res["SurfaceBrush"] = new SolidColorBrush(Color.FromRgb(0xF5, 0xF5, 0xF5));
            res["SurfaceLightBrush"] = new SolidColorBrush(Color.FromRgb(0xFF, 0xFF, 0xFF));
            res["TextPrimaryBrush"] = new SolidColorBrush(Color.FromRgb(0x21, 0x21, 0x21));
            res["TextSecondaryBrush"] = new SolidColorBrush(Color.FromRgb(0x75, 0x75, 0x75));
            res["BorderBrush"] = new SolidColorBrush(Color.FromRgb(0xBD, 0xBD, 0xBD));
        }
        else
        {
            res["SurfaceBrush"] = new SolidColorBrush(Color.FromRgb(0x1E, 0x1E, 0x2E));
            res["SurfaceLightBrush"] = new SolidColorBrush(Color.FromRgb(0x2A, 0x2A, 0x3C));
            res["TextPrimaryBrush"] = new SolidColorBrush(Color.FromRgb(0xE0, 0xE0, 0xE0));
            res["TextSecondaryBrush"] = new SolidColorBrush(Color.FromRgb(0xA0, 0xA0, 0xB0));
            res["BorderBrush"] = new SolidColorBrush(Color.FromRgb(0x3A, 0x3A, 0x4C));
        }
    }

    private static string DetectOsTheme()
    {
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize");
            var val = key?.GetValue("AppsUseLightTheme");
            if (val is int i && i == 1) return "Light";
        }
        catch { }
        return "Dark";
    }
}
