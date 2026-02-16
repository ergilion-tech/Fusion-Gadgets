# MENSEKI - Surface Area / Length / Volume Calculator

An add-in for Autodesk **Fusion 360** that calculates totals for multiple selected entities.

English translation of the original [MENSEKI](https://github.com/kantoku-code/MENSEKI) add-in by kantoku.

## Features

Displays the total area of selected faces, total volume of selected bodies, and total length of selected edges.

Once running, three commands are added to the **Inspect** panel in the Solid, Surface, and Sheet Metal workspaces:

| Command | Description |
|---------|-------------|
| **Length** | Total length of selected edges |
| **Area** | Total area of selected faces |
| **Volume** | Total volume of selected bodies (+ center of gravity for single body) |

## Installation

### Option 1: Self-Extracting Installer (Recommended)

1. Download `MENSEKI_Addin_v0.1.2_Setup.cmd` from the `dist/` folder
2. Double-click to run
3. Follow the on-screen prompts
4. Open Fusion 360 (or restart if already running)
5. Go to **Utilities > Add-Ins** (or press **Shift+S**)
6. Find **MENSEKI_Addin** in the list and click **Run**
7. Optionally check **Run on Startup** for automatic loading

### Option 2: Manual Installation

1. Download and extract the ZIP file
2. Copy the `MENSEKI_Addin` folder to:
   ```
   %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\
   ```
3. Open Fusion 360 (or restart if already running)
4. Go to **Utilities > Add-Ins** (or press **Shift+S**)
5. Find **MENSEKI_Addin** and click **Run**

## Usage

![Toolbar Panel](./images/toolbar_panel.png)

### Dialog

![Dialog](./images/Dialog.png)

### Tooltip

![Tooltip](./images/Tooltip.png)

## Tested Environment

- Fusion 360 Ver 2.0.9305
- Windows 10 64-bit Pro

## Credits

- Original author: [kantoku](https://github.com/kantoku-code)
- Uses [Fusion360AddinSkeleton](https://github.com/tapnair/Fusion360AddinSkeleton) by Patrick Rainsberry
- English translation by Danecca Ltd

## License

MIT License - see [LICENSE](./LICENSE) for details.
