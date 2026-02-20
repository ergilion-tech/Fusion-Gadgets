"""
SpaceMouseDrawingMode v2 — Fusion 360 Add-In
Enables SpaceMouse navigation in Fusion 360's Drawing workspace by reading
SpaceMouse HID data directly (bypassing 3DxWare) and injecting mouse events.

Pan  : tilt SpaceMouse left/right (X) and push forward/back (Z)
Zoom : push SpaceMouse up/down (Y)

See DEVNOTES.md for full background and implementation notes.
Sensitivity can be tuned via the SM Settings button in the SpaceMouse toolbar panel
(Design workspace → SpaceMouse panel → SM Settings).
"""

import adsk.core
import adsk.fusion
import os
import sys
import json
import traceback
from datetime import datetime

# Make our Contents/ folder importable (for spacemouse_hid)
_HERE = os.path.dirname(os.path.realpath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from spacemouse_hid import SpaceMouseListener

# Module-level state
handlers = []
listener = None
LOG_PATH      = os.path.join(_HERE, 'SpaceMouseDrawingMode.log')
SETTINGS_PATH = os.path.join(_HERE, 'settings.json')

# UI identifiers
CMD_ID   = 'SMDrawingSettingsCommand'
PANEL_ID = 'SMDrawingPanel'

# Default sensitivity values (also the fallback when no settings file exists)
DEFAULT_SETTINGS = {
    'PAN_SCALE':  0.08,
    'ZOOM_SCALE': 0.15,
    'DEAD_ZONE':  25,
}


def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')


# --------------------------------------------------------------------------- #
# Settings persistence
# --------------------------------------------------------------------------- #

def load_settings():
    """Load settings from JSON file; fall back to defaults for missing keys."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            for key in DEFAULT_SETTINGS:
                if key in saved:
                    settings[key] = float(saved[key])
    except Exception:
        pass
    return settings


def save_settings(pan_scale, zoom_scale, dead_zone):
    """Write settings to JSON file."""
    data = {
        'PAN_SCALE':  pan_scale,
        'ZOOM_SCALE': zoom_scale,
        'DEAD_ZONE':  dead_zone,
    }
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def apply_settings(settings):
    """Push settings onto the SpaceMouseListener class (affects running listener)."""
    SpaceMouseListener.PAN_SCALE  = settings['PAN_SCALE']
    SpaceMouseListener.ZOOM_SCALE = settings['ZOOM_SCALE']
    SpaceMouseListener.DEAD_ZONE  = int(settings['DEAD_ZONE'])


# --------------------------------------------------------------------------- #
# Workspace event handler
# --------------------------------------------------------------------------- #

class WorkspaceActivatedHandler(adsk.core.WorkspaceEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        global listener
        try:
            ws_id      = args.workspace.id
            is_drawing = (ws_id == 'FusionDocumentationEnvironment')
            if listener:
                listener.drawing_mode = is_drawing
            log(f'Workspace: {ws_id}  drawing_mode={is_drawing}')
        except Exception:
            log(f'WorkspaceActivatedHandler error:\n{traceback.format_exc()}')


# --------------------------------------------------------------------------- #
# Settings dialog — CommandCreated handler
# --------------------------------------------------------------------------- #

class SMSettingsCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd    = args.command
            inputs = cmd.commandInputs

            # Load current values to pre-populate fields
            s = load_settings()

            inputs.addStringValueInput(
                'pan_scale', 'Pan Scale',
                str(s['PAN_SCALE'])
            ).tooltip = (
                'Pixels of pan per SpaceMouse raw unit (X/Z axes). '
                'Increase to pan faster. Default: 0.08'
            )
            inputs.addStringValueInput(
                'zoom_scale', 'Zoom Scale',
                str(s['ZOOM_SCALE'])
            ).tooltip = (
                'Scroll accumulation per SpaceMouse raw unit (Y axis). '
                'Increase to zoom faster. Default: 0.15'
            )
            inputs.addStringValueInput(
                'dead_zone', 'Dead Zone',
                str(int(s['DEAD_ZONE']))
            ).tooltip = (
                'Raw units below which axis movement is ignored. '
                'Decrease if response feels too sluggish. Default: 25'
            )

            on_execute = SMSettingsCommandExecuteHandler()
            cmd.execute.add(on_execute)
            handlers.append(on_execute)

        except Exception:
            log(f'SMSettingsCommandCreatedHandler error:\n{traceback.format_exc()}')


# --------------------------------------------------------------------------- #
# Settings dialog — Execute handler (OK pressed)
# --------------------------------------------------------------------------- #

class SMSettingsCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        global listener
        try:
            app    = adsk.core.Application.get()
            ui     = app.userInterface
            inputs = args.command.commandInputs

            pan_scale_str  = inputs.itemById('pan_scale').value
            zoom_scale_str = inputs.itemById('zoom_scale').value
            dead_zone_str  = inputs.itemById('dead_zone').value

            try:
                pan_scale  = float(pan_scale_str)
                zoom_scale = float(zoom_scale_str)
                dead_zone  = float(dead_zone_str)
            except ValueError:
                ui.messageBox(
                    'Please enter valid numbers for all settings.',
                    'SpaceMouse Settings'
                )
                return

            if pan_scale <= 0 or zoom_scale <= 0 or dead_zone < 0:
                ui.messageBox(
                    'Pan Scale and Zoom Scale must be > 0.\nDead Zone must be >= 0.',
                    'SpaceMouse Settings'
                )
                return

            save_settings(pan_scale, zoom_scale, dead_zone)
            apply_settings({'PAN_SCALE': pan_scale,
                            'ZOOM_SCALE': zoom_scale,
                            'DEAD_ZONE': dead_zone})
            log(f'Settings updated: PAN_SCALE={pan_scale}  '
                f'ZOOM_SCALE={zoom_scale}  DEAD_ZONE={int(dead_zone)}')

            ui.messageBox(
                f'SpaceMouse settings saved!\n\n'
                f'Pan Scale:   {pan_scale}\n'
                f'Zoom Scale:  {zoom_scale}\n'
                f'Dead Zone:   {int(dead_zone)}',
                'SpaceMouse Settings'
            )

        except Exception:
            log(f'SMSettingsCommandExecuteHandler error:\n{traceback.format_exc()}')


# --------------------------------------------------------------------------- #
# Add-in entry points
# --------------------------------------------------------------------------- #

def run(context):
    global listener
    app = adsk.core.Application.get()
    ui  = app.userInterface
    try:
        log('=== SpaceMouseDrawingMode v2 started ===')

        # Load saved settings and apply them before creating the listener
        settings = load_settings()
        apply_settings(settings)
        log(f'Settings: PAN_SCALE={settings["PAN_SCALE"]}  '
            f'ZOOM_SCALE={settings["ZOOM_SCALE"]}  '
            f'DEAD_ZONE={int(settings["DEAD_ZONE"])}')

        # Start the background HID listener thread
        listener = SpaceMouseListener(log_fn=log)
        listener.start()

        # Detect whichever workspace is already active at startup
        try:
            active_ws = ui.activeWorkspace
            if active_ws:
                listener.drawing_mode = (
                    active_ws.id == 'FusionDocumentationEnvironment'
                )
                log(f'Initial workspace: {active_ws.id}  '
                    f'drawing_mode={listener.drawing_mode}')
        except Exception:
            pass

        # Subscribe to workspace changes
        ws_handler = WorkspaceActivatedHandler()
        ui.workspaceActivated.add(ws_handler)
        handlers.append(ws_handler)
        log('workspaceActivated handler registered')

        # ---- UI: Settings button in Design workspace toolbar ----
        icon_path = os.path.join(_HERE, 'resources', 'SMButton')
        settings_cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if not settings_cmd_def:
            settings_cmd_def = ui.commandDefinitions.addButtonDefinition(
                CMD_ID,
                'SM Settings',
                'Adjust SpaceMouse pan/zoom sensitivity and dead zone for Drawing mode',
                icon_path,
            )

        on_created = SMSettingsCommandCreatedHandler()
        settings_cmd_def.commandCreated.add(on_created)
        handlers.append(on_created)

        workspace = ui.workspaces.itemById('FusionSolidEnvironment')
        if workspace:
            panel = workspace.toolbarPanels.itemById(PANEL_ID)
            if not panel:
                panel = workspace.toolbarPanels.add(PANEL_ID, 'SpaceMouse')

            ctrl = panel.controls.itemById(CMD_ID)
            if not ctrl:
                ctrl = panel.controls.addCommand(settings_cmd_def)
            ctrl.isVisible  = True
            ctrl.isPromoted = True

        log('UI panel/button created')

    except Exception:
        log(f'run() error:\n{traceback.format_exc()}')
        try:
            ui.messageBox(
                'SpaceMouseDrawingMode v2 failed to start:\n'
                + traceback.format_exc()
            )
        except Exception:
            pass


def stop(context):
    global listener
    try:
        # Stop the HID listener
        if listener:
            listener.stop()
            listener = None

        # ---- UI cleanup ----
        app = adsk.core.Application.get()
        ui  = app.userInterface

        workspace = ui.workspaces.itemById('FusionSolidEnvironment')
        if workspace:
            # Remove control from any panel it ended up in
            for i in range(workspace.toolbarPanels.count):
                p    = workspace.toolbarPanels.item(i)
                ctrl = p.controls.itemById(CMD_ID)
                if ctrl:
                    ctrl.deleteMe()

            # Remove our panel
            panel = workspace.toolbarPanels.itemById(PANEL_ID)
            if panel:
                panel.deleteMe()

        # Remove command definition
        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()

        handlers.clear()
        log('=== SpaceMouseDrawingMode v2 stopped ===')
    except Exception:
        log(f'stop() error:\n{traceback.format_exc()}')
