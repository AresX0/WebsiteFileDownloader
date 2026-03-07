using System.Diagnostics;
using System.Text.Json;
using WebsiteDownloader.Core.Models;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// Manages application configuration persistence (config.json).
/// Supports fallback paths: app directory → user local app data.
/// </summary>
public static class ConfigManager
{
    private const string ConfigFileName = "config.json";
    private static readonly string AppDataDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "WebsiteDownloader");

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    /// <summary>
    /// Loads config from the most recent config.json found in search paths.
    /// </summary>
    public static AppConfig Load()
    {
        foreach (var path in GetSearchPaths())
        {
            if (!File.Exists(path)) continue;
            try
            {
                var json = File.ReadAllText(path);
                var config = JsonSerializer.Deserialize<AppConfig>(json, JsonOptions);
                if (config != null)
                {
                    Debug.WriteLine($"[Config] Loaded from {path}");
                    return config;
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Config] Error loading {path}: {ex.Message}");
            }
        }

        Debug.WriteLine("[Config] No config found, using defaults");
        return CreateDefault();
    }

    /// <summary>
    /// Saves config with fallback path support.
    /// </summary>
    public static void Save(AppConfig config)
    {
        foreach (var path in GetSavePaths())
        {
            try
            {
                var dir = Path.GetDirectoryName(path);
                if (dir != null && !Directory.Exists(dir))
                    Directory.CreateDirectory(dir);

                var json = JsonSerializer.Serialize(config, JsonOptions);
                File.WriteAllText(path, json);
                Debug.WriteLine($"[Config] Saved to {path}");
                return;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Config] Error saving to {path}: {ex.Message}");
            }
        }

        Debug.WriteLine("[Config] Failed to save config to any path");
    }

    /// <summary>
    /// Export config to a user-chosen file.
    /// </summary>
    public static void Export(AppConfig config, string filePath)
    {
        var json = JsonSerializer.Serialize(config, JsonOptions);
        File.WriteAllText(filePath, json);
    }

    /// <summary>
    /// Import config from a user-chosen file.
    /// </summary>
    public static AppConfig? Import(string filePath)
    {
        if (!File.Exists(filePath)) return null;
        var json = File.ReadAllText(filePath);
        return JsonSerializer.Deserialize<AppConfig>(json, JsonOptions);
    }

    public static AppConfig CreateDefault()
    {
        return new AppConfig
        {
            OutputDirectory = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "Website Downloads"),
            LogDirectory = Path.Combine(AppDataDir, "logs"),
        };
    }

    private static IEnumerable<string> GetSearchPaths()
    {
        yield return Path.Combine(AppContext.BaseDirectory, ConfigFileName);
        yield return Path.Combine(AppDataDir, ConfigFileName);
    }

    private static IEnumerable<string> GetSavePaths()
    {
        yield return Path.Combine(AppContext.BaseDirectory, ConfigFileName);
        yield return Path.Combine(AppDataDir, ConfigFileName);
    }
}
