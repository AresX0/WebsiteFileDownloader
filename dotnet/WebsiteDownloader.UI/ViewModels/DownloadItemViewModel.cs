using WebsiteDownloader.Core.Models;

namespace WebsiteDownloader.UI.ViewModels;

/// <summary>
/// ViewModel wrapper for a single download item in the queue.
/// </summary>
public class DownloadItemViewModel : BindableBase
{
    private bool _isSelected = true;
    private string _status;
    private int _progress;
    private string? _errorMessage;

    public DownloadItemViewModel(DownloadItem item)
    {
        Item = item;
        _status = item.Status;
    }

    public DownloadItem Item { get; }

    public bool IsSelected
    {
        get => _isSelected;
        set => SetProperty(ref _isSelected, value);
    }

    public string Url => Item.Url;
    public string FileName => Item.FileName;
    public string Type => Item.Type;
    public int PageNumber => Item.PageNumber;

    public string Status
    {
        get => _status;
        set => SetProperty(ref _status, value);
    }

    public int Progress
    {
        get => _progress;
        set => SetProperty(ref _progress, value);
    }

    public string? ErrorMessage
    {
        get => _errorMessage;
        set => SetProperty(ref _errorMessage, value);
    }
}
