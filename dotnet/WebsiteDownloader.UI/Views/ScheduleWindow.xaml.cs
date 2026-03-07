using System.Windows;
using WebsiteDownloader.Core.Models;
using WebsiteDownloader.Core.Services;

namespace WebsiteDownloader.UI.Views;

public partial class ScheduleWindow : Window
{
    private readonly DownloadScheduler _scheduler;

    public ScheduleWindow(DownloadScheduler scheduler)
    {
        InitializeComponent();
        _scheduler = scheduler;
        LoadCurrent();
    }

    private readonly Dictionary<DayOfWeek, System.Windows.Controls.CheckBox> _dayChecks = [];

    private void LoadCurrent()
    {
        // Map day checkboxes once loaded
        _dayChecks[DayOfWeek.Monday] = MonCheck;
        _dayChecks[DayOfWeek.Tuesday] = TueCheck;
        _dayChecks[DayOfWeek.Wednesday] = WedCheck;
        _dayChecks[DayOfWeek.Thursday] = ThuCheck;
        _dayChecks[DayOfWeek.Friday] = FriCheck;
        _dayChecks[DayOfWeek.Saturday] = SatCheck;
        _dayChecks[DayOfWeek.Sunday] = SunCheck;

        if (_scheduler.IsActive)
        {
            StatusText.Text = "Schedule is active.";
        }
        else
        {
            StatusText.Text = "No schedule set.";
        }
    }

    private void OnSetSchedule(object sender, RoutedEventArgs e)
    {
        var days = new HashSet<DayOfWeek>();
        foreach (var (day, cb) in _dayChecks)
        {
            if (cb.IsChecked == true) days.Add(day);
        }

        if (days.Count == 0)
        {
            MessageBox.Show("Select at least one day.", "Schedule", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        if (!int.TryParse(HourBox.Text, out var hour) || hour < 0 || hour > 23 ||
            !int.TryParse(MinuteBox.Text, out var minute) || minute < 0 || minute > 59)
        {
            MessageBox.Show("Enter a valid time (HH:MM, 24-hour).", "Schedule", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        var entry = new ScheduleEntry
        {
            Days = days,
            Time = new TimeOnly(hour, minute)
        };

        _scheduler.SetSchedule(entry);
        StatusText.Text = $"Schedule set: {string.Join(", ", days)} at {hour:D2}:{minute:D2}";
    }

    private void OnClearSchedule(object sender, RoutedEventArgs e)
    {
        _scheduler.ClearSchedule();
        foreach (var cb in _dayChecks.Values) cb.IsChecked = false;
        HourBox.Text = "02";
        MinuteBox.Text = "00";
        StatusText.Text = "Schedule cleared.";
    }

    private void OnClose(object sender, RoutedEventArgs e)
    {
        Close();
    }
}
