using System.Diagnostics;
using System.Text.Json;
using WebsiteDownloader.Core.Models;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// Manages download scheduling — checks if a scheduled time matches
/// and triggers downloads at the configured day/time.
/// </summary>
public sealed class DownloadScheduler : IDisposable
{
    private Timer? _timer;
    private ScheduleEntry? _schedule;
    private DateTime _lastTriggered = DateTime.MinValue;
    private bool _disposed;

    /// <summary>Fires when a scheduled download should begin.</summary>
    public event Action? ScheduleTriggered;

    public bool IsActive => _timer != null && _schedule != null;

    public ScheduleEntry? CurrentSchedule => _schedule;

    /// <summary>
    /// Sets and activates a download schedule. Checks every 10 seconds.
    /// </summary>
    public void SetSchedule(ScheduleEntry schedule)
    {
        _schedule = schedule;
        _timer?.Dispose();
        _timer = new Timer(CheckSchedule, null, TimeSpan.FromSeconds(5), TimeSpan.FromSeconds(10));
        Debug.WriteLine($"[Scheduler] Activated: {string.Join(", ", schedule.Days)} at {schedule.Time}");
    }

    /// <summary>
    /// Clears the current schedule.
    /// </summary>
    public void ClearSchedule()
    {
        _timer?.Dispose();
        _timer = null;
        _schedule = null;
        Debug.WriteLine("[Scheduler] Cleared");
    }

    private void CheckSchedule(object? state)
    {
        if (_schedule == null || _disposed) return;

        var now = DateTime.Now;

        // Must match day
        if (!_schedule.Days.Contains(now.DayOfWeek)) return;

        // Must be within 30 seconds of the target time
        var target = new DateTime(now.Year, now.Month, now.Day, _schedule.Time.Hour, _schedule.Time.Minute, 0);
        var diff = Math.Abs((now - target).TotalSeconds);

        if (diff > 30) return;

        // 60-second cooldown to prevent double-triggers
        if ((now - _lastTriggered).TotalSeconds < 60) return;

        _lastTriggered = now;
        _schedule.LastTriggered = now;
        Debug.WriteLine($"[Scheduler] Triggering scheduled download at {now:HH:mm:ss}");
        ScheduleTriggered?.Invoke();
    }

    public void Dispose()
    {
        if (!_disposed)
        {
            _disposed = true;
            _timer?.Dispose();
            _timer = null;
        }
    }
}
