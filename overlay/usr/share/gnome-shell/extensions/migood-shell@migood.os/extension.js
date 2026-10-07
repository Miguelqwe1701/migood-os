// Migood Shell: small changes to GNOME's top bar so it looks like a Googlebook.
//   - the clock + date move from the middle to the left
//   - the "Activities" button is hidden (the Migood button in the dock is the launcher)
//   - the bar is see-through (styles in stylesheet.css)
// Everything is undone in disable(), which GNOME calls when the screen locks.
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class MigoodShell extends Extension {
    enable() {
        const panel = Main.panel;

        // Clock: remember where it was, then put it first on the left.
        this._clock = panel.statusArea.dateMenu.container;
        this._clockParent = this._clock.get_parent();
        this._clockIndex = this._clockParent.get_children().indexOf(this._clock);
        this._clockParent.remove_child(this._clock);
        panel._leftBox.insert_child_at_index(this._clock, 0);

        this._activities = panel.statusArea.activities?.container;
        this._activities?.hide();

        panel.add_style_class_name('migood-panel');
    }

    disable() {
        const panel = Main.panel;
        panel.remove_style_class_name('migood-panel');
        this._activities?.show();
        if (this._clock) {
            this._clock.get_parent()?.remove_child(this._clock);
            this._clockParent.insert_child_at_index(this._clock, this._clockIndex);
        }
        this._clock = this._clockParent = this._activities = null;
    }
}
