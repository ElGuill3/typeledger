import gettext
from datetime import date

from gi.repository import Adw, Gtk

from typeledger.core.layout import load_layout
from typeledger.core.progress import (
    char_error_rates,
    daily_summaries,
    key_heat,
    overview,
)
from typeledger.ui.chart_view import ChartView
from typeledger.ui.keyboard_view import KeyboardView

_ = gettext.gettext
ngettext = gettext.ngettext

RANGES = (7, 30, 90)
DEFAULT_RANGE = 30
MIN_SAMPLES = 5  # matches char_error_rates' default
NO_VALUE = "—"


def _days(count):
    return ngettext("%d day", "%d days", count) % count


def _duration(seconds):
    minutes = round(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return _("{hours} h {minutes} min").format(hours=hours, minutes=minutes)
    return _("{minutes} min").format(minutes=minutes)


class ProgressPage(Adw.Bin):
    """Streak, totals, daily WPM/accuracy charts and the error heatmap."""

    __gtype_name__ = "TypeLedgerProgressPage"

    def __init__(self, storage, *, today=None, **kwargs):
        super().__init__(**kwargs)
        self._storage = storage
        self._today = today or date.today
        self._results = []
        self._layout_id = None
        self._layout = None
        self.wpm_points = []
        self.accuracy_points = []
        self.heat = {}

        self.empty_page = Adw.StatusPage(
            icon_name="x-office-presentation-symbolic",
            title=_("No sessions yet"),
            description=_("Complete a practice session to see your progress here."),
        )
        self.content_page = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            child=Adw.Clamp(maximum_size=900, child=self._build_content()),
        )
        self.stack = Gtk.Stack()
        self.stack.add_named(self.empty_page, "empty")
        self.stack.add_named(self.content_page, "content")
        self.set_child(self.stack)

    # Layout

    def _build_content(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(12)
        box.set_margin_end(12)

        box.append(self._build_streak_card())
        box.append(self._build_overview_row())

        header = Gtk.Box(spacing=12)
        header.append(Gtk.Label(label=_("Daily progress"), xalign=0, hexpand=True,
                                css_classes=["title-4"]))
        self.range_group = Adw.ToggleGroup(css_classes=["round"])
        for days in RANGES:
            self.range_group.add(Adw.Toggle(name=str(days), label=_days(days)))
        self.range_group.set_active_name(str(DEFAULT_RANGE))
        self.range_group.connect("notify::active-name", lambda *_args: self._update_charts())
        header.append(self.range_group)
        box.append(header)

        self.wpm_chart = ChartView()
        self.wpm_chart.set_title(_("WPM"))
        self.wpm_chart.set_y_range(0.0, None)
        self.wpm_chart.set_value_format("{:.0f}".format)
        box.append(_card(self.wpm_chart))

        self.accuracy_chart = ChartView()
        self.accuracy_chart.set_title(_("Accuracy"))
        self.accuracy_chart.set_y_range(0.0, 100.0)
        self.accuracy_chart.set_value_format("{:.0f}%".format)
        box.append(_card(self.accuracy_chart))

        box.append(Gtk.Label(label=_("Errors by key"), xalign=0, css_classes=["title-4"]))
        self.keyboard = KeyboardView()
        box.append(_card(self.keyboard))
        box.append(
            Gtk.Label(
                label=_(
                    "Redder keys have more errors. Characters typed fewer than "
                    "{count} times are not counted."
                ).format(count=MIN_SAMPLES),
                xalign=0,
                wrap=True,
                css_classes=["dim-label", "caption"],
            )
        )
        return box

    def _build_streak_card(self):
        self.streak_label = Gtk.Label(css_classes=["title-1"])
        self.longest_label = Gtk.Label(css_classes=["dim-label"])
        self.today_label = Gtk.Label(css_classes=["heading"])
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.append(Gtk.Label(label=_("Current streak"), css_classes=["dim-label"]))
        content.append(self.streak_label)
        content.append(self.today_label)
        content.append(self.longest_label)
        return _card(content)

    def _build_overview_row(self):
        # Cards wrap onto more lines when the window is too narrow for five.
        row = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            homogeneous=True,
            min_children_per_line=2,
            max_children_per_line=5,
            column_spacing=12,
            row_spacing=12,
            can_focus=False,
        )
        self.overview_box = row
        self.total_sessions_label = _stat(row, _("Sessions"))
        self.total_time_label = _stat(row, _("Practice time"))
        self.best_wpm_label = _stat(row, _("Best WPM"))
        self.recent_wpm_label = _stat(row, _("WPM, last 7 days"))
        self.recent_accuracy_label = _stat(row, _("Accuracy, last 7 days"))
        return row

    # Data

    def refresh(self, layout_id):
        """Reload the history and redraw everything for ``layout_id``."""
        self._results = [stored.result for stored in self._storage.list_sessions()]
        if layout_id != self._layout_id:
            self._layout_id = layout_id
            self._layout = load_layout(layout_id)
            self.keyboard.set_layout(self._layout)

        if not self._results:
            self.stack.set_visible_child(self.empty_page)
            return
        self.stack.set_visible_child(self.content_page)

        summary = overview(self._results, self._today())
        streak = summary.streak
        self.streak_label.set_label("🔥 " + _days(streak.current))
        self.longest_label.set_label(
            _("Longest streak: {days}").format(days=_days(streak.longest))
        )
        self.today_label.set_label(
            _("Practiced today") if streak.practiced_today
            else _("Practice today to keep your streak")
        )

        self.total_sessions_label.set_label(str(summary.total_sessions))
        self.total_time_label.set_label(_duration(summary.total_seconds))
        self.best_wpm_label.set_label(str(round(summary.best_wpm)))
        if summary.recent_sessions:
            self.recent_wpm_label.set_label(str(round(summary.recent_avg_wpm)))
            self.recent_accuracy_label.set_label(
                "{}%".format(round(summary.recent_avg_accuracy * 100))
            )
        else:
            self.recent_wpm_label.set_label(NO_VALUE)
            self.recent_accuracy_label.set_label(NO_VALUE)

        self._update_charts()
        self.heat = key_heat(
            self._layout, char_error_rates(self._results, min_samples=MIN_SAMPLES)
        )
        self.keyboard.set_heat(self.heat)

    def _update_charts(self):
        days = int(self.range_group.get_active_name() or DEFAULT_RANGE)
        summaries = daily_summaries(self._results, days=days, today=self._today())
        self.wpm_points = [
            (s.day, s.avg_wpm if s.sessions else None) for s in summaries
        ]
        self.accuracy_points = [
            (s.day, s.avg_accuracy * 100 if s.sessions else None) for s in summaries
        ]
        self.wpm_chart.set_points(self.wpm_points)
        self.accuracy_chart.set_points(self.accuracy_points)


def _card(child):
    child.set_margin_top(12)
    child.set_margin_bottom(12)
    child.set_margin_start(12)
    child.set_margin_end(12)
    card = Gtk.Box(css_classes=["card"])
    child.set_hexpand(True)
    card.append(child)
    return card


def _stat(row, caption):
    value = Gtk.Label(css_classes=["title-2", "numeric"])
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.append(value)
    # Capping the natural width keeps long captions from widening every card.
    box.append(Gtk.Label(label=caption, wrap=True, max_width_chars=12,
                         justify=Gtk.Justification.CENTER,
                         css_classes=["dim-label", "caption"]))
    row.append(_card(box))
    return value
