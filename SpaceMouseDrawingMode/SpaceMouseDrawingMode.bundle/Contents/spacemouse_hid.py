"""
spacemouse_hid.py
Background HID listener for SpaceMouse navigation in Fusion 360 Drawing mode.

Reads SpaceMouse axis data via Windows Raw Input API (RIDEV_INPUTSINK flag
allows receiving HID data even when Fusion is in focus / owns the foreground).
When drawing_mode is True, converts SpaceMouse axes to mouse events via SendInput:
  X axis  → middle-button mouse drag horizontal  (pan left/right)
  Z axis  → middle-button mouse drag vertical    (pan up/down)
  Y axis  → scroll wheel reversed                (zoom)

3DxWare continues running normally for Design mode — no conflict.
No external dependencies: pure ctypes + Python standard library.
"""

import ctypes
import struct
import threading

# --------------------------------------------------------------------------- #
# Windows API handles
# --------------------------------------------------------------------------- #
user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
WM_INPUT        = 0x00FF
WM_DESTROY      = 0x0002

RIDEV_INPUTSINK = 0x00000100
RIDEV_REMOVE    = 0x00000001
RID_INPUT       = 0x10000003
RIM_TYPEHID     = 2

HID_USAGE_PAGE_GENERIC          = 0x01
HID_USAGE_GENERIC_MULTIAXISCTRL = 0x08   # Multi-axis Controller (SpaceMouse)

INPUT_MOUSE            = 0
MOUSEEVENTF_MOVE       = 0x0001
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040
MOUSEEVENTF_WHEEL      = 0x0800

# --------------------------------------------------------------------------- #
# Windows structures (sized for 64-bit; ctypes handles alignment automatically)
# --------------------------------------------------------------------------- #

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ('usUsagePage', ctypes.c_ushort),
        ('usUsage',     ctypes.c_ushort),
        ('dwFlags',     ctypes.c_uint32),
        ('hwndTarget',  ctypes.c_void_p),
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ('dwType',  ctypes.c_uint32),
        ('dwSize',  ctypes.c_uint32),
        ('hDevice', ctypes.c_size_t),   # HANDLE  — pointer-sized
        ('wParam',  ctypes.c_size_t),   # WPARAM  — pointer-sized
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx',          ctypes.c_long),
        ('dy',          ctypes.c_long),
        ('mouseData',   ctypes.c_uint32),
        ('dwFlags',     ctypes.c_uint32),
        ('time',        ctypes.c_uint32),
        ('dwExtraInfo', ctypes.c_size_t),  # ULONG_PTR — pointer-sized
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _anonymous_ = ('_input',)
    _fields_ = [
        ('type',   ctypes.c_uint32),
        ('_input', _INPUT_UNION),
    ]

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_size_t,   # LRESULT
    ctypes.c_void_p,   # HWND
    ctypes.c_uint32,   # UINT  (message ID)
    ctypes.c_size_t,   # WPARAM
    ctypes.c_size_t,   # LPARAM
)

class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ('style',         ctypes.c_uint32),
        ('lpfnWndProc',   WNDPROC),
        ('cbClsExtra',    ctypes.c_int),
        ('cbWndExtra',    ctypes.c_int),
        ('hInstance',     ctypes.c_void_p),
        ('hIcon',         ctypes.c_void_p),
        ('hCursor',       ctypes.c_void_p),
        ('hbrBackground', ctypes.c_void_p),
        ('lpszMenuName',  ctypes.c_wchar_p),
        ('lpszClassName', ctypes.c_wchar_p),
    ]

class MSG(ctypes.Structure):
    _fields_ = [
        ('hwnd',    ctypes.c_void_p),
        ('message', ctypes.c_uint32),
        ('wParam',  ctypes.c_size_t),
        ('lParam',  ctypes.c_size_t),
        ('time',    ctypes.c_uint32),
        ('pt_x',    ctypes.c_long),
        ('pt_y',    ctypes.c_long),
    ]

# --------------------------------------------------------------------------- #
# SpaceMouseListener
# --------------------------------------------------------------------------- #

class SpaceMouseListener:
    """
    Start with start().  Set .drawing_mode = True to enable mouse injection.
    Call stop() on add-in unload.

    Tunable class attributes:
        PAN_SCALE   pixels per SpaceMouse raw unit for X/Z pan
        ZOOM_SCALE  scroll accumulation per SpaceMouse raw unit for Y zoom
        DEAD_ZONE   raw units below which axis is treated as zero
    """
    PAN_SCALE  = 0.08
    ZOOM_SCALE = 0.15
    DEAD_ZONE  = 25

    def __init__(self, log_fn=None):
        self._log        = log_fn or (lambda m: None)
        self.drawing_mode = False
        self._running    = False
        self._thread     = None
        self._hwnd       = None
        self._proc_ref   = None   # keeps WNDPROC callback alive (prevents GC)
        self._mid_held  = False
        self._zoom_acc  = 0.0

    def start(self):
        self._running = True
        self._thread  = threading.Thread(
            target=self._run, daemon=True, name='SMHIDThread'
        )
        self._thread.start()

    def stop(self):
        self._running = False
        hwnd = self._hwnd
        if hwnd:
            # Wake the message loop so it can exit cleanly
            user32.PostMessageW(ctypes.c_void_p(hwnd), WM_DESTROY, 0, 0)
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._mid_held:
            self._release_middle()

    # ------------------------------------------------------------------ #
    # Thread body
    # ------------------------------------------------------------------ #

    def _run(self):
        try:
            self._message_loop()
        except Exception as exc:
            self._log(f'SpaceMouseListener thread error: {exc}')

    def _message_loop(self):
        hInst    = kernel32.GetModuleHandleW(None)
        cls_name = 'SMHIDWnd_v2'

        proc           = WNDPROC(self._wnd_proc)
        self._proc_ref = proc  # must stay alive for duration of loop

        wcls = WNDCLASSW()
        wcls.lpfnWndProc   = proc
        wcls.hInstance     = hInst
        wcls.lpszClassName = cls_name

        atom = user32.RegisterClassW(ctypes.byref(wcls))
        if not atom:
            err = kernel32.GetLastError()
            if err != 1410:  # 1410 = ERROR_CLASS_ALREADY_EXISTS — harmless on restart
                self._log(f'RegisterClassW failed: error {err}')
                return

        # Message-only window: invisible, no taskbar/tray entry
        HWND_MESSAGE = ctypes.c_void_p(-3)
        hwnd = user32.CreateWindowExW(
            0, cls_name, cls_name, 0,
            0, 0, 0, 0,
            HWND_MESSAGE, None, hInst, None
        )
        if not hwnd:
            self._log(f'CreateWindowExW failed: error {kernel32.GetLastError()}')
            return
        self._hwnd = hwnd

        # Register for SpaceMouse (Multi-axis Controller) raw HID input.
        # RIDEV_INPUTSINK = receive data even when our window is NOT foreground.
        rid = RAWINPUTDEVICE(
            HID_USAGE_PAGE_GENERIC,
            HID_USAGE_GENERIC_MULTIAXISCTRL,
            RIDEV_INPUTSINK,
            hwnd,
        )
        if not user32.RegisterRawInputDevices(
                ctypes.byref(rid), 1, ctypes.sizeof(rid)):
            self._log(
                f'RegisterRawInputDevices failed: error {kernel32.GetLastError()}'
            )
            return

        self._log('SpaceMouseListener: message loop running')

        msg = MSG()
        while self._running:
            # GetMessageW(NULL hwnd) receives all thread messages incl. WM_QUIT
            r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r == 0 or r == -1:   # 0 = WM_QUIT posted, -1 = error
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Unregister HID device on exit
        rid_rm = RAWINPUTDEVICE(
            HID_USAGE_PAGE_GENERIC,
            HID_USAGE_GENERIC_MULTIAXISCTRL,
            RIDEV_REMOVE,
            None,
        )
        user32.RegisterRawInputDevices(
            ctypes.byref(rid_rm), 1, ctypes.sizeof(rid_rm)
        )
        self._hwnd = None
        self._log('SpaceMouseListener: message loop stopped')

    # ------------------------------------------------------------------ #
    # Window procedure (runs on the background thread via DispatchMessage)
    # ------------------------------------------------------------------ #

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            if self.drawing_mode:
                self._on_raw_input(lparam)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(
            ctypes.c_void_p(hwnd), msg,
            ctypes.c_size_t(wparam), ctypes.c_size_t(lparam),
        )

    # ------------------------------------------------------------------ #
    # Raw input parsing
    # ------------------------------------------------------------------ #

    def _on_raw_input(self, lparam):
        hri    = ctypes.c_void_p(lparam)
        hdr_sz = ctypes.sizeof(RAWINPUTHEADER)
        sz     = ctypes.c_uint(0)

        # First call with NULL buffer returns required size
        user32.GetRawInputData(hri, RID_INPUT, None, ctypes.byref(sz), hdr_sz)
        if not sz.value:
            return

        buf = ctypes.create_string_buffer(sz.value)
        if user32.GetRawInputData(
                hri, RID_INPUT, buf, ctypes.byref(sz), hdr_sz) == 0xFFFFFFFF:
            return

        # Verify it is a HID report (not mouse/keyboard)
        hdr = RAWINPUTHEADER.from_buffer_copy(buf.raw[:hdr_sz])
        if hdr.dwType != RIM_TYPEHID:
            return

        # RAWHID layout immediately after header:
        #   DWORD dwSizeHid  (bytes per report)
        #   DWORD dwCount    (number of reports)
        #   BYTE  bRawData[dwSizeHid * dwCount]
        off = hdr_sz
        if len(buf.raw) < off + 8:
            return
        dw_size_hid, dw_count = struct.unpack_from('<II', buf.raw, off)
        off += 8

        if dw_count == 0 or dw_size_hid < 7:
            return
        hid = buf.raw[off: off + dw_size_hid]
        if len(hid) < 7:
            return

        # SpaceMouse Report ID 1 = Translation
        # Layout: [id=1, X_lo, X_hi, Y_lo, Y_hi, Z_lo, Z_hi]
        if hid[0] == 1:
            x, y, z = struct.unpack_from('<hhh', hid, 1)
            self._apply(x, y, z)

    # ------------------------------------------------------------------ #
    # Axis → mouse event conversion
    # ------------------------------------------------------------------ #

    def _apply(self, x, y, z):
        dz    = self.DEAD_ZONE
        pan_x = int(x * self.PAN_SCALE) if abs(x) >= dz else 0
        pan_y = int(z * self.PAN_SCALE) if abs(z) >= dz else 0   # Z → vertical pan
        zoom  = (-y * self.ZOOM_SCALE)  if abs(y) >= dz else 0.0 # Y → zoom (reversed)

        if pan_x or pan_y:
            if not self._mid_held:
                self._press_middle()
            self._move(pan_x, pan_y)
        elif self._mid_held:
            self._release_middle()

        if zoom:
            self._zoom_acc += zoom
            while abs(self._zoom_acc) >= 120:
                tick = 120 if self._zoom_acc > 0 else -120
                self._scroll(tick)
                self._zoom_acc -= tick

    # ------------------------------------------------------------------ #
    # SendInput helpers
    # ------------------------------------------------------------------ #

    def _make(self, flags, dx=0, dy=0, data=0):
        i                = INPUT()
        i.type           = INPUT_MOUSE
        i.mi.dx          = dx
        i.mi.dy          = dy
        i.mi.mouseData   = ctypes.c_uint32(data).value
        i.mi.dwFlags     = flags
        i.mi.time        = 0
        i.mi.dwExtraInfo = 0
        return i

    def _send(self, *inputs):
        arr = (INPUT * len(inputs))(*inputs)
        user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

    def _press_middle(self):
        self._send(self._make(MOUSEEVENTF_MIDDLEDOWN))
        self._mid_held = True

    def _release_middle(self):
        self._send(self._make(MOUSEEVENTF_MIDDLEUP))
        self._mid_held = False

    def _move(self, dx, dy):
        self._send(self._make(MOUSEEVENTF_MOVE, dx, dy))

    def _scroll(self, amount):
        self._send(self._make(MOUSEEVENTF_WHEEL, data=amount))
