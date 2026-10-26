import gettext
import math

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Adw, Gtk, Pango, PangoCairo  # noqa: E402

_ = gettext.gettext

PADDING = 12  # px around the drawing
LABEL_GAP = 6  # px between labels and the plot area
LINE_WIDTH = 2.5
MARKER_RADIUS = 3.5
TARGET_INTERVALS = 4  # gridline intervals aimed for by the auto range
HEADROOM = 0.1  # fraction of the data span added above (and below) the data
MIDDLE_LABEL_MIN_POINTS = 8  # more than 7 points get a middle x label


def _nice_step(raw):
    """Smallest 1/2/2.5/5 x 10^n step that is at least raw."""
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 2.5, 5, 10):
        if factor * magnitude >= raw * (1 - 1e-9):
            return factor * magnitude
    return 10 * magnitude


def _auto_ticks(values, minimum, maximum):
    """Gridline values (ascending) covering values and the fixed bounds."""
    if minimum is not None and maximum is not None and maximum > minimum:
        step = (maximum - minimum) / TARGET_INTERVALS
        return [minimum + i * step for i in range(TARGET_INTERVALS + 1)]

    data_min, data_max = min(values), max(values)
    low = minimum if minimum is not None else data_min
    high = maximum if maximum is not None else data_max
    span = high - low
    if span <= 0:
        # Constant data: open a range around it instead of dividing by zero.
        span = abs(high) or 1.0
        if minimum is not None and maximum is None:
            high = low + span
    if maximum is None:
        high = max(high, low) + span * HEADROOM
    if minimum is None:
        low = min(low, high) - span * HEADROOM
        if data_min >= 0 > low:
            low = 0.0

    step = _nice_step((high - low) / TARGET_INTERVALS)
    if minimum is None:
        low = math.floor(low / step) * step
    count = max(1, math.ceil((high - low) / step - 1e-9))
    if count < 3:
        step /= 2
        count = max(1, math.ceil((high - low) / step - 1e-9))
    return [low + i * step for i in range(count + 1)]


class ChartView(Gtk.DrawingArea):
    """Line chart of one value per day; None values are gaps in the line."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._points = []
        self._minimum = 0.0
        self._maximum = None
        self._format = lambda value: f"{value:g}"
        self._title = ""
        self.set_content_height(180)
        self.set_hexpand(True)
        self.set_draw_func(lambda _area, cr, width, height: self.draw_to(cr, width, height))

    def set_points(self, points):
        self._points = list(points)
        self.queue_draw()

    def set_y_range(self, minimum=0.0, maximum=None):
        self._minimum = minimum
        self._maximum = maximum
        self.queue_draw()

    def set_value_format(self, fmt):
        self._format = fmt
        self.queue_draw()

    def set_title(self, text):
        self._title = text
        self.queue_draw()

    def draw_to(self, cr, width, height):
        """Render the chart onto a cairo context of the given size."""
        if width <= 2 * PADDING or height <= 2 * PADDING:
            return

        fg = self.get_color()
        accent = Adw.StyleManager.get_default().get_accent_color_rgba()
        font = Pango.FontDescription.from_string("Sans")
        font.set_absolute_size(11 * Pango.SCALE)
        title_font = font.copy()
        title_font.set_weight(Pango.Weight.BOLD)

        top = PADDING
        if self._title:
            title = self._text_layout(cr, title_font, self._title)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, fg.alpha)
            cr.move_to(PADDING, top)
            PangoCairo.show_layout(cr, title)
            top += title.get_pixel_extents()[1].height + LABEL_GAP

        values = [value for _day, value in self._points if value is not None]
        if not values:
            message = self._text_layout(cr, font, _("No sessions in this period"))
            _ink, logical = message.get_pixel_extents()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.55 * fg.alpha)
            cr.move_to((width - logical.width) / 2, (top + height - logical.height) / 2)
            PangoCairo.show_layout(cr, message)
            return

        ticks = _auto_ticks(values, self._minimum, self._maximum)
        tick_layouts = [self._text_layout(cr, font, self._format(tick)) for tick in ticks]
        label_width = max(layout.get_pixel_extents()[1].width for layout in tick_layouts)
        label_height = tick_layouts[0].get_pixel_extents()[1].height

        left = PADDING + label_width + LABEL_GAP
        right = width - PADDING
        bottom = height - PADDING - label_height - LABEL_GAP
        top += label_height / 2
        if right - left <= 2 * MARKER_RADIUS or bottom <= top:
            return
        low, high = ticks[0], ticks[-1]

        def y_for(value):
            return bottom - (value - low) / (high - low) * (bottom - top)

        # Gridlines with their value labels.
        cr.set_line_width(1.0)
        for tick, layout in zip(ticks, tick_layouts):
            y = round(y_for(tick)) + 0.5
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.15 * fg.alpha)
            cr.move_to(left, y)
            cr.line_to(right, y)
            cr.stroke()
            _ink, logical = layout.get_pixel_extents()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.7 * fg.alpha)
            cr.move_to(left - LABEL_GAP - logical.width, y - logical.height / 2)
            PangoCairo.show_layout(cr, layout)

        # Points are spread over the plot, inset so edge markers stay visible.
        inner_left = left + MARKER_RADIUS + 1
        inner_right = right - MARKER_RADIUS - 1
        count = len(self._points)

        def x_for(index):
            if count == 1:
                return (inner_left + inner_right) / 2
            return inner_left + index * (inner_right - inner_left) / (count - 1)

        # Day labels: first, last, and a middle one for longer ranges.
        indexes = sorted({0, count - 1} | ({count // 2} if count >= MIDDLE_LABEL_MIN_POINTS else set()))
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.7 * fg.alpha)
        for index in indexes:
            layout = self._text_layout(cr, font, self._points[index][0].strftime("%d/%m"))
            _ink, logical = layout.get_pixel_extents()
            x = x_for(index) - logical.width / 2
            x = max(left, min(x, right - logical.width))
            cr.move_to(x, bottom + LABEL_GAP)
            PangoCairo.show_layout(cr, layout)

        # The line, broken at None values, then a marker on every value.
        cr.save()
        cr.rectangle(left - MARKER_RADIUS, top - MARKER_RADIUS,
                     right - left + 2 * MARKER_RADIUS, bottom - top + 2 * MARKER_RADIUS)
        cr.clip()
        cr.set_source_rgba(accent.red, accent.green, accent.blue, 1.0)
        cr.set_line_width(LINE_WIDTH)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        drawing = False
        for index, (_day, value) in enumerate(self._points):
            if value is None:
                drawing = False
                continue
            if drawing:
                cr.line_to(x_for(index), y_for(value))
            else:
                cr.move_to(x_for(index), y_for(value))
                drawing = True
        cr.stroke()
        for index, (_day, value) in enumerate(self._points):
            if value is None:
                continue
            cr.new_sub_path()
            cr.arc(x_for(index), y_for(value), MARKER_RADIUS, 0, 2 * math.pi)
            cr.fill()
        cr.restore()

    @staticmethod
    def _text_layout(cr, font, text):
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(font)
        layout.set_text(text, -1)
        return layout
