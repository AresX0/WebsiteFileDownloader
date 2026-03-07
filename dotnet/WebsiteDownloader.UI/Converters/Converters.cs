using System.Globalization;
using System.Windows;
using System.Windows.Data;

namespace WebsiteDownloader.UI.Converters;

/// <summary>
/// Converts boolean true to Visible, false to Collapsed.
/// </summary>
public class BoolToVisibilityConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture) =>
        value is true ? Visibility.Visible : Visibility.Collapsed;

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
        value is Visibility.Visible;
}

/// <summary>
/// Converts boolean true to Collapsed, false to Visible (inverse).
/// </summary>
public class InverseBoolToVisibilityConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture) =>
        value is true ? Visibility.Collapsed : Visibility.Visible;

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
        value is Visibility.Collapsed;
}

/// <summary>
/// Converts file size in bytes to human-readable string.
/// </summary>
public class FileSizeConverter : IValueConverter
{
    private static readonly string[] Suffixes = ["B", "KB", "MB", "GB", "TB"];

    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
    {
        if (value is not long bytes || bytes <= 0)
            return "—";

        var order = 0;
        var size = (double)bytes;

        while (size >= 1024 && order < Suffixes.Length - 1)
        {
            order++;
            size /= 1024;
        }

        return $"{size:0.##} {Suffixes[order]}";
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
        throw new NotImplementedException();
}

/// <summary>
/// Inverts a boolean value.
/// </summary>
public class InverseBoolConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture) =>
        value is bool b ? !b : value;

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
        value is bool b ? !b : value;
}
