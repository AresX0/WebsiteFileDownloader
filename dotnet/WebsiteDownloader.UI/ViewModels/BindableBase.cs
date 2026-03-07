using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace WebsiteDownloader.UI.ViewModels;

/// <summary>
/// Base class for all ViewModels. Implements INotifyPropertyChanged.
/// Same pattern as PlatypusToolsNew.
/// </summary>
public abstract class BindableBase : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;

    protected void RaisePropertyChanged([CallerMemberName] string? name = null) =>
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));

    protected void OnPropertyChanged([CallerMemberName] string? name = null) =>
        RaisePropertyChanged(name);

    protected bool SetProperty<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value)) return false;
        field = value;
        RaisePropertyChanged(propertyName);
        return true;
    }
}
