using System.Diagnostics;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// Ensures only one instance of the application runs at a time.
/// Uses a named system mutex (Windows) for cross-process locking.
/// </summary>
public sealed class SingleInstanceLock : IDisposable
{
    private const string MutexName = "Local\\WebsiteDownloader_SingleInstance";
    private Mutex? _mutex;
    private bool _hasLock;

    /// <summary>
    /// Attempts to acquire the single-instance lock.
    /// Returns true if this is the first instance, false if another is already running.
    /// </summary>
    public bool TryAcquire()
    {
        try
        {
            _mutex = new Mutex(false, MutexName);

            try
            {
                _hasLock = _mutex.WaitOne(0);
            }
            catch (AbandonedMutexException)
            {
                // Previous owner crashed — we now own the mutex
                _hasLock = true;
            }

            if (!_hasLock)
            {
                Debug.WriteLine("[SingleInstance] Another instance is already running");
                _mutex.Dispose();
                _mutex = null;
                return false;
            }

            Debug.WriteLine("[SingleInstance] Lock acquired");
            return true;
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[SingleInstance] Error: {ex.Message}");
            return true; // If mutex fails, allow running
        }
    }

    public void Dispose()
    {
        if (_hasLock && _mutex != null)
        {
            try
            {
                _mutex.ReleaseMutex();
            }
            catch { /* best effort */ }
        }

        _mutex?.Dispose();
        _mutex = null;
        _hasLock = false;
    }
}
