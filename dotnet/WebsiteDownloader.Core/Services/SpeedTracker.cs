using System.Diagnostics;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// Tracks download speed and estimates time remaining (ETA).
/// Thread-safe; updated per download chunk.
/// </summary>
public class SpeedTracker
{
    private readonly Stopwatch _stopwatch = new();
    private long _bytesDownloaded;
    private long _totalBytes;
    private readonly Queue<(DateTime time, long bytes)> _samples = new();
    private readonly object _lock = new();
    private const int MaxSamples = 20;
    private const double SampleWindowSeconds = 5.0;

    public double SpeedBytesPerSecond { get; private set; }
    public double SpeedKbps => SpeedBytesPerSecond / 1024.0;
    public TimeSpan Elapsed => _stopwatch.Elapsed;

    public TimeSpan EstimatedTimeRemaining
    {
        get
        {
            if (SpeedBytesPerSecond <= 0 || _totalBytes <= 0)
                return TimeSpan.Zero;

            var remaining = _totalBytes - _bytesDownloaded;
            if (remaining <= 0) return TimeSpan.Zero;

            return TimeSpan.FromSeconds(remaining / SpeedBytesPerSecond);
        }
    }

    public string SpeedText
    {
        get
        {
            if (SpeedBytesPerSecond <= 0) return "—";
            if (SpeedKbps < 1024) return $"{SpeedKbps:F0} KB/s";
            return $"{SpeedKbps / 1024:F1} MB/s";
        }
    }

    public string EtaText
    {
        get
        {
            var eta = EstimatedTimeRemaining;
            if (eta <= TimeSpan.Zero) return "—";
            if (eta.TotalHours >= 1) return $"{eta.Hours}h {eta.Minutes}m";
            if (eta.TotalMinutes >= 1) return $"{eta.Minutes}m {eta.Seconds}s";
            return $"{eta.Seconds}s";
        }
    }

    public void Start(long totalBytes = 0)
    {
        _totalBytes = totalBytes;
        _bytesDownloaded = 0;
        SpeedBytesPerSecond = 0;

        lock (_lock)
        {
            _samples.Clear();
        }

        _stopwatch.Restart();
    }

    public void Update(long bytesDownloaded, long totalBytes = 0)
    {
        _bytesDownloaded = bytesDownloaded;
        if (totalBytes > 0) _totalBytes = totalBytes;

        var now = DateTime.UtcNow;

        lock (_lock)
        {
            _samples.Enqueue((now, bytesDownloaded));

            // Remove old samples outside the window
            while (_samples.Count > MaxSamples ||
                   (_samples.Count > 1 && (now - _samples.Peek().time).TotalSeconds > SampleWindowSeconds))
            {
                _samples.Dequeue();
            }

            // Calculate speed from the sample window
            if (_samples.Count >= 2)
            {
                var oldest = _samples.Peek();
                var elapsed = (now - oldest.time).TotalSeconds;
                if (elapsed > 0)
                {
                    SpeedBytesPerSecond = (bytesDownloaded - oldest.bytes) / elapsed;
                }
            }
        }
    }

    public void Stop()
    {
        _stopwatch.Stop();
    }

    public void Reset()
    {
        _stopwatch.Reset();
        _bytesDownloaded = 0;
        _totalBytes = 0;
        SpeedBytesPerSecond = 0;

        lock (_lock)
        {
            _samples.Clear();
        }
    }
}
