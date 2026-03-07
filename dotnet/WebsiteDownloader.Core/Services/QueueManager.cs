using System.Diagnostics;
using System.Text.Json;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// Manages the URL download queue with persistence (queue_state.json).
/// Supports save/restore across app restarts.
/// </summary>
public static class QueueManager
{
    private const string QueueFileName = "queue_state.json";

    private static readonly string AppDataDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "WebsiteDownloader");

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    public static QueueState Load()
    {
        foreach (var path in GetSearchPaths())
        {
            if (!File.Exists(path)) continue;
            try
            {
                var json = File.ReadAllText(path);
                var state = JsonSerializer.Deserialize<QueueState>(json, JsonOptions);
                if (state?.Urls is { Count: > 0 })
                {
                    Debug.WriteLine($"[Queue] Loaded {state.Urls.Count} URLs from {path}");
                    return state;
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Queue] Error loading {path}: {ex.Message}");
            }
        }

        return new QueueState();
    }

    public static void Save(QueueState state)
    {
        foreach (var path in GetSavePaths())
        {
            try
            {
                var dir = Path.GetDirectoryName(path);
                if (dir != null && !Directory.Exists(dir))
                    Directory.CreateDirectory(dir);

                var json = JsonSerializer.Serialize(state, JsonOptions);
                File.WriteAllText(path, json);
                Debug.WriteLine($"[Queue] Saved {state.Urls.Count} URLs to {path}");
                return;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Queue] Error saving to {path}: {ex.Message}");
            }
        }
    }

    private static IEnumerable<string> GetSearchPaths()
    {
        yield return Path.Combine(AppContext.BaseDirectory, QueueFileName);
        yield return Path.Combine(AppDataDir, QueueFileName);
    }

    private static IEnumerable<string> GetSavePaths()
    {
        yield return Path.Combine(AppContext.BaseDirectory, QueueFileName);
        yield return Path.Combine(AppDataDir, QueueFileName);
    }
}

public class QueueState
{
    public List<string> Urls { get; set; } = [];
    public int ProcessedCount { get; set; }
}
