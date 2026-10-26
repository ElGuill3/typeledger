// TypeLedger Streak: shows the TypeLedger practice streak in the top bar.
// The data comes from the summary.json file exported by the app.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GioUnix from 'gi://GioUnix';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Pango from 'gi://Pango';
import St from 'gi://St';

import {Extension, gettext as _, ngettext} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {computeStreak, localIsoDate, newestSummary, parseSummary} from './streak.js';

const APP_ID = 'io.github.elguill3.TypeLedger';
const RELOAD_DELAY_MS = 250;
// The day check is re-armed at least this often so a suspend over midnight
// is noticed soon after resume.
const MAX_DAY_CHECK_S = 60 * 60;

function summaryPaths() {
    return [
        GLib.build_filenamev([GLib.get_user_data_dir(), 'typeledger', 'summary.json']),
        GLib.build_filenamev([GLib.get_home_dir(), '.var', 'app', APP_ID, 'data', 'typeledger', 'summary.json']),
    ];
}

function secondsUntilTomorrow() {
    const now = GLib.DateTime.new_now_local();
    const tomorrow = now.add_days(1);
    const midnight = GLib.DateTime.new_local(
        tomorrow.get_year(), tomorrow.get_month(), tomorrow.get_day_of_month(), 0, 0, 0);
    // difference() is in microseconds; add a second to land just after midnight.
    return Math.max(1, Math.ceil(midnight.difference(now) / GLib.USEC_PER_SEC) + 1);
}

const StreakIndicator = GObject.registerClass(
class StreakIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.5, _('TypeLedger Streak'));

        this._label = new St.Label({
            text: '🔥 0',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'typeledger-streak-label',
        });
        // St.Label ellipsizes by default, which makes its minimum width ~1px.
        // A crowded top bar then shrinks this button down to its padding and
        // the streak disappears, so keep the full text as the minimum width.
        this._label.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
        this.add_child(this._label);

        this._currentItem = this._addInfoItem();
        this._longestItem = this._addInfoItem();
        this._todayItem = this._addInfoItem();
        this._recentItem = this._addInfoItem();
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this.menu.addAction(_('Open TypeLedger'), () => this._openApp());
        this.menu.connectObject('open-state-changed', (_menu, open) => {
            if (open)
                this._sync();
        }, this);

        this._summary = null;
        this._generation = 0;
        this._reloadId = 0;
        this._dayCheckId = 0;
        this._cancellable = new Gio.Cancellable();
        this._files = summaryPaths().map(path => Gio.File.new_for_path(path));
        this._monitors = [];
        for (const file of this._files) {
            try {
                // Monitors also report files that do not exist yet once they appear.
                const monitor = file.monitor_file(Gio.FileMonitorFlags.NONE, null);
                monitor.connectObject('changed', () => this._queueReload(), this);
                this._monitors.push(monitor);
            } catch (e) {
                console.error(`TypeLedger Streak: cannot monitor ${file.get_path()}: ${e.message}`);
            }
        }

        this._sync();
        this._scheduleDayCheck();
        this._reload();
    }

    _addInfoItem() {
        const item = new PopupMenu.PopupMenuItem('', {reactive: false, can_focus: false});
        this.menu.addMenuItem(item);
        return item;
    }

    _queueReload() {
        if (this._reloadId)
            return;
        this._reloadId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, RELOAD_DELAY_MS, () => {
            this._reloadId = 0;
            this._reload();
            return GLib.SOURCE_REMOVE;
        });
    }

    _reload() {
        const generation = ++this._generation;
        Promise.all(this._files.map(file => this._loadSummary(file))).then(summaries => {
            if (generation !== this._generation || this._cancellable.is_cancelled())
                return;
            this._summary = newestSummary(summaries);
            this._sync();
        }).catch(e => console.error(`TypeLedger Streak: reload failed: ${e.message}`));
    }

    _loadSummary(file) {
        return new Promise(resolve => {
            file.load_contents_async(this._cancellable, (source, result) => {
                try {
                    const [, contents] = source.load_contents_finish(result);
                    resolve(parseSummary(new TextDecoder().decode(contents)));
                } catch (e) {
                    if (!e.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.NOT_FOUND) &&
                        !e.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                        console.warn(`TypeLedger Streak: cannot read ${file.get_path()}: ${e.message}`);
                    resolve(null);
                }
            });
        });
    }

    _scheduleDayCheck() {
        const seconds = Math.min(secondsUntilTomorrow(), MAX_DAY_CHECK_S);
        this._dayCheckId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, seconds, () => {
            this._dayCheckId = 0;
            this._sync();
            this._scheduleDayCheck();
            return GLib.SOURCE_REMOVE;
        });
    }

    _sync() {
        const summary = this._summary;
        const hasPractice = summary !== null && summary.practiced_days.length > 0;
        const streak = hasPractice
            ? computeStreak(summary.practiced_days, localIsoDate(new Date()))
            : {current: 0, practicedToday: false};

        this._label.text = `🔥 ${streak.current}`;
        if (streak.practicedToday)
            this._label.remove_style_class_name('typeledger-streak-pending');
        else
            this._label.add_style_class_name('typeledger-streak-pending');

        if (!hasPractice) {
            this._currentItem.label.text = _('No practice yet');
            for (const item of [this._longestItem, this._todayItem, this._recentItem])
                item.visible = false;
            return;
        }

        this._currentItem.label.text = ngettext(
            'Current streak: %d day', 'Current streak: %d days', streak.current
        ).replace('%d', String(streak.current));
        // The exported longest streak can lag behind a run that grew today.
        const longest = Math.max(summary.longest_streak, streak.current);
        this._longestItem.label.text = ngettext(
            'Longest streak: %d day', 'Longest streak: %d days', longest
        ).replace('%d', String(longest));
        this._todayItem.label.text = streak.practicedToday
            ? _('Practiced today')
            : _('Not practiced yet today');
        this._recentItem.label.text = summary.recent_sessions > 0
            ? _('Last 7 days: {wpm} WPM · {accuracy}%')
                .replace('{wpm}', String(Math.round(summary.recent_avg_wpm)))
                .replace('{accuracy}', String(Math.round(summary.recent_avg_accuracy * 100)))
            : _('No sessions in the last 7 days');
        for (const item of [this._longestItem, this._todayItem, this._recentItem])
            item.visible = true;
    }

    _openApp() {
        try {
            let app = null;
            try {
                app = GioUnix.DesktopAppInfo.new(`${APP_ID}.desktop`);
            } catch (e) {
                console.warn(`TypeLedger Streak: ${APP_ID}.desktop lookup failed: ${e.message}`);
            }
            if (app)
                app.launch([], global.create_app_launch_context(0, -1));
            else
                GLib.spawn_command_line_async('typeledger');
        } catch (e) {
            console.error(`TypeLedger Streak: cannot open TypeLedger: ${e.message}`);
        }
    }

    destroy() {
        this._cancellable.cancel();
        if (this._reloadId) {
            GLib.source_remove(this._reloadId);
            this._reloadId = 0;
        }
        if (this._dayCheckId) {
            GLib.source_remove(this._dayCheckId);
            this._dayCheckId = 0;
        }
        for (const monitor of this._monitors) {
            monitor.disconnectObject(this);
            monitor.cancel();
        }
        this._monitors = [];
        this._files = [];
        this._summary = null;
        super.destroy();
    }
});

export default class TypeLedgerStreakExtension extends Extension {
    enable() {
        this._indicator = new StreakIndicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
