using System.IO;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// File-based logger that writes to disk. Maintains both a general log
/// and a separate error log, matching the Python version's dual-file approach.
/// </summary>
public sealed class FileLogger : IDisposable
{
    private readonly string _logDirectory;
    private readonly StreamWriter? _logWriter;
    private readonly StreamWriter? _errorWriter;
    private readonly object _lock = new();
    private bool _disposed;

    public string LogFilePath { get; }
    public string ErrorLogFilePath { get; }

    public FileLogger(string logDirectory)
    {
        _logDirectory = logDirectory;

        try
        {
            if (!Directory.Exists(logDirectory))
                Directory.CreateDirectory(logDirectory);

            LogFilePath = Path.Combine(logDirectory, "website_downloader.log");
            ErrorLogFilePath = Path.Combine(logDirectory, "error.log");

            _logWriter = new StreamWriter(LogFilePath, append: true) { AutoFlush = true };
            _errorWriter = new StreamWriter(ErrorLogFilePath, append: true) { AutoFlush = true };

            Log("INFO", "=== Website Downloader started ===");
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"[FileLogger] Init error: {ex.Message}");
            LogFilePath = string.Empty;
            ErrorLogFilePath = string.Empty;
        }
    }

    public void Log(string level, string message)
    {
        if (_disposed) return;
        var line = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] {message}";

        lock (_lock)
        {
            try
            {
                _logWriter?.WriteLine(line);
            }
            catch { /* best effort */ }
        }
    }

    public void Info(string message) => Log("INFO", message);
    public void Warn(string message) => Log("WARN", message);
    public void Debug(string message) => Log("DEBUG", message);

    public void Error(string message, Exception? ex = null)
    {
        var errorLine = ex != null
            ? $"{message}\n  Exception: {ex.GetType().Name}: {ex.Message}\n  StackTrace: {ex.StackTrace}"
            : message;

        Log("ERROR", errorLine);

        lock (_lock)
        {
            try
            {
                _errorWriter?.WriteLine($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {errorLine}");
            }
            catch { /* best effort */ }
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        Log("INFO", "=== Website Downloader stopped ===");

        lock (_lock)
        {
            _logWriter?.Dispose();
            _errorWriter?.Dispose();
        }
    }
}
