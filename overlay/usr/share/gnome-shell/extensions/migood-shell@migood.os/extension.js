// Migood Shell: the Migood OS look on top of GNOME.
// The taskbar itself is Dash to Panel (settings in /etc/dconf/db/local.d/00-migood);
// this extension only adds the "migood" style class, so stylesheet.css can
// give the bar, the launcher and Quick Settings the Migood Home look.
// Everything is undone in disable(), which GNOME calls when the screen locks.
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class MigoodShell extends Extension {
    enable() {
        Main.uiGroup.add_style_class_name('migood');
        Main.panel.add_style_class_name('migood-panel');
    }

    disable() {
        Main.uiGroup.remove_style_class_name('migood');
        Main.panel.remove_style_class_name('migood-panel');
    }
}
