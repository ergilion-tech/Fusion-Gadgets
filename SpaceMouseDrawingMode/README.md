# SpaceMouseDrawingMode

**Version:** 1.0.1
**Platform:** Fusion 360 (Windows only)
**Author:** DANECCA

---

## What It Does

Fusion 360's Drawing workspace ignores 3DxWare entirely — the SpaceMouse does nothing in 2D Drawing mode out of the box. This add-in fixes that.

It runs a background listener that reads SpaceMouse axis data directly via the Windows Raw Input API (bypassing 3DxWare), then converts it to synthetic mouse events using SendInput:

| SpaceMouse Axis | Drawing Mode Action |
|-----------------|---------------------|
| X (left/right)  | Pan left / right (middle-button drag) |
| Z (forward/back)| Pan up / down (middle-button drag) |
| Y (push down/pull up) | Zoom out / in (scroll wheel) |

3DxWare continues running normally — Design mode is unaffected.

---

## Requirements

- **Fusion 360** (any recent version, Windows)
- **3Dconnexion 3DxWare** driver installed (device must be connected)
- No additional Python packages — pure ctypes, standard library only

---

## Installation

### Option A — Deploy.bat (recommended)

1. Download or clone this repository
2. Navigate to the `SpaceMouseDrawingMode/` folder
3. Double-click **`Deploy.bat`**
4. Follow the on-screen prompts (it will warn you if Fusion 360 is running)

The script copies the add-in to:
```
%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\SpaceMouseDrawingMode\
```

### Option B — Manual install

1. Copy the entire `SpaceMouseDrawingMode.bundle\Contents\` folder to:
   ```
   %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\SpaceMouseDrawingMode\
   ```
   (Create the `SpaceMouseDrawingMode` folder if it doesn't exist.)

2. The final folder structure should look like:
   ```
   AddIns\
   └── SpaceMouseDrawingMode\
       ├── SpaceMouseDrawingMode.manifest
       ├── SpaceMouseDrawingMode.py
       ├── spacemouse_hid.py
       └── resources\
           └── SMButton\
               ├── 16x16.png
               ├── 32x32.png
               └── 64x64.png
   ```

---

## First Run

1. Open (or restart) Fusion 360
2. Open the **Scripts and Add-Ins** dialog: **Utilities → Add-Ins** (or press `Shift+S`)
3. Under **My Add-Ins**, find **SpaceMouseDrawingMode** and click **Run**
   - Tick **Run on Startup** to have it start automatically every time
4. A **SpaceMouse** panel will appear in the **Design** workspace toolbar
5. Click **SM Settings** to adjust sensitivity:
   - **Pan Scale** — how many pixels per SpaceMouse raw unit (default `0.08`)
   - **Zoom Scale** — scroll accumulation per SpaceMouse raw unit (default `0.15`)
   - **Dead Zone** — raw units below which the axis is ignored (default `25`)

---

## Using It

- **Design workspace**: SpaceMouse works as normal via 3DxWare (the add-in is passive)
- **Drawing workspace**: SpaceMouse pans and zooms the drawing sheet using the axis mapping above
- Switching between workspaces is seamless — no manual toggling required

---

## Settings

Settings are saved to `settings.json` next to the add-in files and persist across Fusion restarts. If you need to reset to defaults, delete that file.

---

## Uninstall

1. In Fusion 360, open **Utilities → Add-Ins**, find **SpaceMouseDrawingMode**, and click **Stop**
2. Delete the folder:
   ```
   %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\SpaceMouseDrawingMode\
   ```

---

## How It Works (Technical)

The add-in spawns a background thread that:

1. Creates an invisible message-only window (`HWND_MESSAGE`)
2. Registers for SpaceMouse HID data via `RegisterRawInputDevices` with the `RIDEV_INPUTSINK` flag (receives data even when Fusion owns the foreground)
3. Parses HID Report ID 1 (Translation): `[id, X_lo, X_hi, Y_lo, Y_hi, Z_lo, Z_hi]` — three signed 16-bit values
4. When Fusion is in the Drawing workspace, converts axis values to `SendInput` calls:
   - X/Z → `MOUSEEVENTF_MIDDLEDOWN` + `MOUSEEVENTF_MOVE` + `MOUSEEVENTF_MIDDLEUP`
   - Y → `MOUSEEVENTF_WHEEL`

The main add-in file hooks `workspaceActivated` and `workspaceDeactivated` events to toggle the listener on/off between Drawing and Design workspaces.

---

## Known Limitations

- **Windows only** — Raw Input and SendInput are Windows APIs
- During SpaceMouse panning, the regular mouse cursor moves with the middle-button drag (this is a fundamental Windows limitation — true cursor independence is not achievable via SendInput in Fusion 360's Drawing mode)
- Rotation axes are not mapped (Fusion Drawing is 2D — rotation has no use)
