// Test-only extension loaded next to TypeLedger Streak in a throwaway headless
// GNOME Shell (see tests/test_extension.py). It crowds the right side of the
// top bar until the streak button gets less than its natural width, measures
// the label and writes the result to $TYPELEDGER_PROBE_OUT/result.json.

import GLib from 'gi://GLib';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const UUID = 'typeledger@elguill3.github.io';
const POLL_MS = 200;
const TIMEOUT_MS = 20000;
// Width left for the streak button once the filler is in: below its natural
// width but above its padding, like a crowded top bar.
const SQUEEZED_WIDTH = 20;

function measure(label) {
    const [minWidth, natWidth] = label.get_preferred_width(-1);
    const box = label.get_allocation_box();
    return {
        text: label.text,
        minWidth,
        natWidth,
        allocWidth: box.x2 - box.x1,
        visible: label.visible,
        mapped: label.mapped,
        opacity: label.opacity,
    };
}

function measureBox(actor) {
    const [minWidth, natWidth] = actor.get_preferred_width(-1);
    const box = actor.get_allocation_box();
    return {minWidth, natWidth, allocWidth: box.x2 - box.x1};
}

export default class PanelProbeExtension extends Extension {
    enable() {
        this._outDir = GLib.getenv('TYPELEDGER_PROBE_OUT');
        this._filler = null;
        this._elapsed = 0;
        this._sourceId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, POLL_MS, () => this._step());
    }

    _step() {
        try {
            return this._measureStep();
        } catch (e) {
            this._finish({error: `${e}\n${e.stack}`});
            return GLib.SOURCE_REMOVE;
        }
    }

    _measureStep() {
        this._elapsed += POLL_MS;
        if (this._elapsed > TIMEOUT_MS) {
            this._finish({error: 'timed out waiting for the indicator'});
            return GLib.SOURCE_REMOVE;
        }
        const indicator = Main.panel.statusArea[UUID];
        const label = indicator?.get_first_child();
        if (!label?.mapped || label.get_allocation_box().x2 === 0)
            return GLib.SOURCE_CONTINUE;

        if (!this._filler) {
            this._relaxed = measure(label);
            this._relaxedButton = measureBox(indicator.container);
            const [, centerWidth] = Main.panel._centerBox.get_preferred_width(-1);
            const [, rightWidth] = Main.panel._rightBox.get_preferred_width(-1);
            const [, buttonWidth] = indicator.container.get_preferred_width(-1);
            const sideWidth = Math.floor((Main.panel.width - centerWidth) / 2);
            const fillerWidth = Math.max(0, sideWidth - (rightWidth - buttonWidth) - SQUEEZED_WIDTH);
            this._filler = new St.Widget({width: fillerWidth});
            Main.panel._rightBox.insert_child_at_index(this._filler, 0);
            this._fillerWidth = fillerWidth;
            this._sideWidth = sideWidth;
            return GLib.SOURCE_CONTINUE;
        }

        this._finish({
            relaxed: this._relaxed,
            squeezed: measure(label),
            fillerWidth: this._fillerWidth,
            sideWidth: this._sideWidth,
            relaxedButton: this._relaxedButton,
            squeezedButton: measureBox(indicator.container),
            squeezedRightBox: measureBox(Main.panel._rightBox),
        });
        return GLib.SOURCE_REMOVE;
    }

    _finish(result) {
        this._sourceId = 0;
        if (this._outDir)
            GLib.file_set_contents(GLib.build_filenamev([this._outDir, 'result.json']), JSON.stringify(result));
    }

    disable() {
        if (this._sourceId)
            GLib.source_remove(this._sourceId);
        this._sourceId = 0;
        this._filler?.destroy();
        this._filler = null;
    }
}
