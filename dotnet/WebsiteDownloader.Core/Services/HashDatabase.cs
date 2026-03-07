using System.Collections.Concurrent;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;

namespace WebsiteDownloader.Core.Services;

/// <summary>
/// SHA-256 hash database for duplicate file detection.
/// Maintains a persistent hash file (<c>existing_hashes.txt</c>) and an in-memory
/// cache with a configurable TTL to avoid redundant disk scans.
/// Compatible with the Python original's hash file format: <c>hash\tpath</c> per line.
/// </summary>
public sealed class HashDatabase : IDisposable
{
    private const string HashFileName = "existing_hashes.txt";
    private const string CacheFileName = ".hash_cache.json";
    private static readonly TimeSpan DefaultCacheTtl = TimeSpan.FromHours(4);

    private readonly ConcurrentDictionary<string, string> _hashes = new(StringComparer.OrdinalIgnoreCase);
    private readonly object _fileLock = new();
    private string _outputDirectory = string.Empty;
    private bool _disposed;

    /// <summary>Number of hashes currently tracked.</summary>
    public int Count => _hashes.Count;

    /// <summary>
    /// Scans an output directory for existing files, computing SHA-256 hashes
    /// for each. Skips files already in the database. Reports progress.
    /// </summary>
    public async Task ScanExistingFilesAsync(
        string outputDirectory,
        IProgress<(int scanned, int total, string currentFile)>? progress = null,
        CancellationToken cancellationToken = default)
    {
        _outputDirectory = outputDirectory;

        // Try to load from cache first
        if (TryLoadFromCache(outputDirectory))
        {
            progress?.Report((_hashes.Count, _hashes.Count, "(loaded from cache)"));
            return;
        }

        // Load any existing hash file entries
        LoadHashFile(outputDirectory);

        // Find all files that aren't in the hash database yet
        var files = Directory.Exists(outputDirectory)
            ? Directory.GetFiles(outputDirectory, "*", SearchOption.AllDirectories)
                .Where(f => !Path.GetFileName(f).StartsWith('.') && Path.GetFileName(f) != HashFileName)
                .ToArray()
            : [];

        if (files.Length == 0)
        {
            SaveCache(outputDirectory);
            return;
        }

        // Use up to 50% of CPU threads for hashing (like the Python version)
        var maxParallelism = Math.Max(1, Environment.ProcessorCount / 2);
        var scanned = 0;

        await Task.Run(() =>
        {
            Parallel.ForEach(files,
                new ParallelOptions
                {
                    MaxDegreeOfParallelism = maxParallelism,
                    CancellationToken = cancellationToken
                },
                file =>
                {
                    // Skip if we already have a hash for this path
                    var relativePath = Path.GetRelativePath(outputDirectory, file);
                    if (_hashes.Values.Any(v => v.Equals(relativePath, StringComparison.OrdinalIgnoreCase)))
                    {
                        Interlocked.Increment(ref scanned);
                        return;
                    }

                    var hash = ComputeFileHash(file);
                    if (hash != null)
                    {
                        _hashes.TryAdd(hash, relativePath);
                    }

                    var current = Interlocked.Increment(ref scanned);
                    progress?.Report((current, files.Length, Path.GetFileName(file)));
                });
        }, cancellationToken);

        // Persist everything
        SaveHashFile(outputDirectory);
        SaveCache(outputDirectory);
    }

    /// <summary>
    /// Checks whether a SHA-256 hash already exists in the database.
    /// </summary>
    public bool HashExists(string hash) => _hashes.ContainsKey(hash);

    /// <summary>
    /// Checks whether a specific file (by relative path) is already tracked.
    /// </summary>
    public bool FileExists(string relativePath) =>
        _hashes.Values.Any(v => v.Equals(relativePath, StringComparison.OrdinalIgnoreCase));

    /// <summary>
    /// Registers a newly downloaded file's hash.
    /// </summary>
    public void RegisterFile(string hash, string relativePath)
    {
        _hashes.TryAdd(hash, relativePath);

        if (!string.IsNullOrEmpty(_outputDirectory))
        {
            AppendHashEntry(_outputDirectory, hash, relativePath);
        }
    }

    /// <summary>
    /// Clears the in-memory cache and the on-disk cache file.
    /// Forces a full rescan on next <see cref="ScanExistingFilesAsync"/>.
    /// </summary>
    public void ClearCache()
    {
        _hashes.Clear();

        if (!string.IsNullOrEmpty(_outputDirectory))
        {
            var cacheFile = Path.Combine(_outputDirectory, CacheFileName);
            if (File.Exists(cacheFile))
                File.Delete(cacheFile);
        }
    }

    /// <summary>
    /// Computes the SHA-256 hash of a file on disk.
    /// Returns lowercase hex string, or null on I/O error.
    /// </summary>
    public static string? ComputeFileHash(string filePath)
    {
        try
        {
            using var sha = SHA256.Create();
            using var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.Read, 65536);
            var hashBytes = sha.ComputeHash(stream);
            return Convert.ToHexStringLower(hashBytes);
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Hash] Error hashing {filePath}: {ex.Message}");
            return null;
        }
    }

    #region Persistence

    private void LoadHashFile(string outputDirectory)
    {
        var hashFilePath = Path.Combine(outputDirectory, HashFileName);
        if (!File.Exists(hashFilePath))
            return;

        try
        {
            foreach (var line in File.ReadLines(hashFilePath))
            {
                var parts = line.Split('\t', 2);
                if (parts.Length == 2 && !string.IsNullOrWhiteSpace(parts[0]))
                {
                    _hashes.TryAdd(parts[0].Trim(), parts[1].Trim());
                }
            }

            Debug.WriteLine($"[Hash] Loaded {_hashes.Count} hashes from {hashFilePath}");
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Hash] Error loading hash file: {ex.Message}");
        }
    }

    private void SaveHashFile(string outputDirectory)
    {
        var hashFilePath = Path.Combine(outputDirectory, HashFileName);

        try
        {
            lock (_fileLock)
            {
                using var writer = new StreamWriter(hashFilePath, append: false);
                foreach (var kvp in _hashes)
                {
                    writer.WriteLine($"{kvp.Key}\t{kvp.Value}");
                }
            }

            Debug.WriteLine($"[Hash] Saved {_hashes.Count} hashes to {hashFilePath}");
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Hash] Error saving hash file: {ex.Message}");
        }
    }

    private void AppendHashEntry(string outputDirectory, string hash, string relativePath)
    {
        var hashFilePath = Path.Combine(outputDirectory, HashFileName);

        try
        {
            lock (_fileLock)
            {
                File.AppendAllText(hashFilePath, $"{hash}\t{relativePath}\n");
            }
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Hash] Error appending: {ex.Message}");
        }
    }

    #endregion

    #region Cache

    private bool TryLoadFromCache(string outputDirectory)
    {
        var cacheFile = Path.Combine(outputDirectory, CacheFileName);
        if (!File.Exists(cacheFile))
            return false;

        try
        {
            var json = File.ReadAllText(cacheFile);
            var cache = JsonSerializer.Deserialize<HashCacheData>(json);

            if (cache == null || cache.Entries == null)
                return false;

            // Check TTL
            var age = DateTime.UtcNow - cache.Timestamp;
            if (age > DefaultCacheTtl)
            {
                Debug.WriteLine($"[Hash] Cache expired ({age.TotalHours:F1}h old)");
                return false;
            }

            // Check that the directory file count roughly matches
            var currentFileCount = Directory.Exists(outputDirectory)
                ? Directory.GetFiles(outputDirectory, "*", SearchOption.AllDirectories).Length
                : 0;

            if (Math.Abs(currentFileCount - cache.FileCount) > 10)
            {
                Debug.WriteLine($"[Hash] Cache stale: {cache.FileCount} cached vs {currentFileCount} actual files");
                return false;
            }

            foreach (var entry in cache.Entries)
            {
                _hashes.TryAdd(entry.Key, entry.Value);
            }

            Debug.WriteLine($"[Hash] Loaded {_hashes.Count} hashes from cache ({age.TotalMinutes:F0}m old)");
            return true;
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Hash] Error loading cache: {ex.Message}");
            return false;
        }
    }

    private void SaveCache(string outputDirectory)
    {
        var cacheFile = Path.Combine(outputDirectory, CacheFileName);

        try
        {
            var currentFileCount = Directory.Exists(outputDirectory)
                ? Directory.GetFiles(outputDirectory, "*", SearchOption.AllDirectories).Length
                : 0;

            var cache = new HashCacheData
            {
                Timestamp = DateTime.UtcNow,
                FileCount = currentFileCount,
                Entries = _hashes.ToDictionary(kvp => kvp.Key, kvp => kvp.Value)
            };

            var json = JsonSerializer.Serialize(cache, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(cacheFile, json);
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Hash] Error saving cache: {ex.Message}");
        }
    }

    private sealed class HashCacheData
    {
        public DateTime Timestamp { get; set; }
        public int FileCount { get; set; }
        public Dictionary<string, string>? Entries { get; set; }
    }

    #endregion

    public void Dispose()
    {
        if (!_disposed)
        {
            _disposed = true;
            // Save cache on dispose if we have an output directory
            if (!string.IsNullOrEmpty(_outputDirectory) && !_hashes.IsEmpty)
            {
                SaveCache(_outputDirectory);
            }
        }
    }
}
