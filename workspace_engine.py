"""
Zenith OS - Workspace Engine
============================
Reliable capture / storage / launch of app workspaces on Windows.

Key design points
-----------------
* True open-window detection (EnumWindows + DWM cloak + owner/tool-window filters).
* Packaged (Microsoft Store / MSIX) apps are stored as ``shell:AppsFolder\\<AUMID>``
  instead of their versioned ``C:\\Program Files\\WindowsApps\\...`` exe path, because
  those paths break on every app update and cannot be launched directly.
* Stale paths self-heal at launch time (Squirrel ``app-x.y.z`` / Roblox ``version-*``
  folders, updated Store packages, or fall back to resolving the app by name).
* No silent failures: every launch reports exactly which apps started and which failed.
* Uses private ``ctypes.WinDLL`` instances so it never mutates the shared
  ``ctypes.windll.*`` function signatures used by other modules (e.g. the hotkey thread).
"""
import os
import re
import json
import glob
import time
import uuid
import shutil
import threading
import subprocess
import ctypes
from ctypes import wintypes

WS_FILE = os.path.expanduser("~/.zenith_workspaces.json")
APPS_FOLDER_PREFIX = "shell:AppsFolder\\"
_LOCK = threading.RLock()

# ----------------------------------------------------------------------------
# Private Win32 bindings
# ----------------------------------------------------------------------------
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_dwmapi = ctypes.WinDLL("dwmapi")
_shell32 = ctypes.WinDLL("shell32")
_ole32 = ctypes.WinDLL("ole32")

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
_user32.EnumWindows.restype = wintypes.BOOL
_user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]
_user32.EnumChildWindows.restype = wintypes.BOOL
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.IsWindowVisible.restype = wintypes.BOOL
_user32.IsIconic.argtypes = [wintypes.HWND]
_user32.IsIconic.restype = wintypes.BOOL
_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetWindowLongW.restype = ctypes.c_long
_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_user32.GetWindowTextLengthW.restype = ctypes.c_int
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetWindowTextW.restype = ctypes.c_int
_user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetClassNameW.restype = ctypes.c_int
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetWindowRect.restype = wintypes.BOOL
_user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
_user32.GetWindow.restype = wintypes.HWND

_dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
_dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long

_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
_kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
try:
    _kernel32.GetApplicationUserModelId.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_uint32), wintypes.LPWSTR]
    _kernel32.GetApplicationUserModelId.restype = ctypes.c_long
    _HAS_APPMODEL = True
except AttributeError:
    _HAS_APPMODEL = False

_ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
_ole32.CoInitializeEx.restype = ctypes.c_long
_ole32.CoUninitialize.argtypes = []
_ole32.CoUninitialize.restype = None


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def from_str(cls, s):
        return cls.from_buffer_copy(uuid.UUID(s).bytes_le)


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", wintypes.DWORD)]


class _PROPVARIANT(ctypes.Structure):
    # 24 bytes on x64 / 16 on x86: vt + 3 reserved WORDs + 16/8-byte union
    _fields_ = [("vt", ctypes.c_ushort), ("r1", wintypes.WORD), ("r2", wintypes.WORD),
                ("r3", wintypes.WORD), ("val", ctypes.c_void_p), ("pad", ctypes.c_void_p)]


_shell32.SHGetPropertyStoreForWindow.argtypes = [wintypes.HWND, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
_shell32.SHGetPropertyStoreForWindow.restype = ctypes.c_long
_ole32.PropVariantClear.argtypes = [ctypes.POINTER(_PROPVARIANT)]
_ole32.PropVariantClear.restype = ctypes.c_long

_IID_IPropertyStore = _GUID.from_str("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")
_PKEY_AppUserModel_ID = _PROPERTYKEY(_GUID.from_str("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), 5)

GWL_EXSTYLE = -20
GW_OWNER = 4
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
DWMWA_CLOAKED = 14
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
VT_LPWSTR = 31

_SKIP_TITLES = {
    "program manager", "windows input experience", "microsoft text input application",
    "zenith os", "zenith os settings", "zenith settings", "dynamic island", "task switching",
    "nvidia geforce overlay", "default ime", "msctfime ui", "new workspace", "edit workspace",
}
_SKIP_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow",
    "Windows.UI.Core.CoreWindow", "IME", "MSCTFIME UI", "TopLevelWindowForOverflowXamlIsland",
    "XamlExplorerHostIslandWindow", "ForegroundStaging", "MultitaskingViewFrame",
}
_SKIP_EXES = {
    "searchhost.exe", "searchapp.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
    "textinputhost.exe", "lockapp.exe", "widgets.exe", "widgetservice.exe", "gamebar.exe",
    "gamebarftserver.exe", "nvcontainer.exe", "nvidia share.exe", "securityhealthsystray.exe",
    "runtimebroker.exe", "svchost.exe", "conhost.exe", "dwm.exe", "csrss.exe", "sihost.exe",
    "python.exe", "pythonw.exe", "py.exe", "pyw.exe",
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _log(msg):
    try:
        print(f"[Workspace] {msg}")
    except Exception:
        pass


def is_apps_folder_token(token: str) -> bool:
    return str(token).lower().startswith("shell:appsfolder\\")


def _is_uri(token: str) -> bool:
    # "whatsapp:", "ms-settings:", "steam://rungameid/1", "https://..." but NOT "C:\..."
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.\-]+):", token)
    return bool(m) and len(m.group(1)) > 1


def display_name(token: str) -> str:
    """Human friendly label for a stored workspace entry."""
    t = str(token or "").strip()
    if not t:
        return ""
    if is_apps_folder_token(t):
        aumid = t[len(APPS_FOLDER_PREFIX):]
        if "!" in aumid:
            pkg, app_id = aumid.split("!", 1)
            if app_id.lower() not in ("app", "application", "main", "app.main"):
                return app_id.split(".")[-1]
            return pkg.split("_")[0].split(".")[-1]
        return aumid.split(".")[-1]
    if _is_uri(t) and not os.path.isabs(t):
        return t.split(":")[0].capitalize()
    base = os.path.basename(t.replace("/", "\\").rstrip("\\")) or t
    for ext in (".exe", ".lnk", ".url", ".bat", ".cmd"):
        if base.lower().endswith(ext):
            base = base[: -len(ext)]
            break
    return base


def _process_image_path(pid: int) -> str:
    h = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if _kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        _kernel32.CloseHandle(h)


def _process_aumid(pid: int):
    """AUMID of a packaged (MSIX/Store) process, else None."""
    if not _HAS_APPMODEL:
        return None
    h = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        length = ctypes.c_uint32(0)
        rc = _kernel32.GetApplicationUserModelId(h, ctypes.byref(length), None)
        if rc != 122 or length.value == 0:  # ERROR_INSUFFICIENT_BUFFER means "packaged"
            return None
        buf = ctypes.create_unicode_buffer(length.value)
        if _kernel32.GetApplicationUserModelId(h, ctypes.byref(length), buf) == 0:
            return buf.value or None
        return None
    finally:
        _kernel32.CloseHandle(h)


def _window_aumid(hwnd):
    """Explicit AUMID stored on a window (works for UWP ApplicationFrameWindow)."""
    ppv = ctypes.c_void_p()
    try:
        hr = _shell32.SHGetPropertyStoreForWindow(hwnd, ctypes.byref(_IID_IPropertyStore), ctypes.byref(ppv))
    except Exception:
        return None
    if hr != 0 or not ppv.value:
        return None
    result = None
    try:
        vtbl = ctypes.cast(ppv, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        get_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_PROPERTYKEY),
                                       ctypes.POINTER(_PROPVARIANT))(vtbl[5])
        pv = _PROPVARIANT()
        if get_value(ppv, ctypes.byref(_PKEY_AppUserModel_ID), ctypes.byref(pv)) == 0:
            if pv.vt == VT_LPWSTR and pv.val:
                result = ctypes.wstring_at(pv.val) or None
            _ole32.PropVariantClear(ctypes.byref(pv))
    except Exception:
        result = None
    finally:
        try:
            release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
                ctypes.cast(ppv, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[2])
            release(ppv)
        except Exception:
            pass
    return result


def _aumid_from_windowsapps_path(path: str):
    """C:\\Program Files\\WindowsApps\\<PkgFullName>\\sub\\App.exe -> 'Family!AppId' (or None)."""
    norm = os.path.normpath(path)
    parts = norm.split(os.sep)
    low = [p.lower() for p in parts]
    if "windowsapps" not in low:
        return None
    idx = low.index("windowsapps")
    if idx + 2 >= len(parts):
        return None
    pkg_full = parts[idx + 1]
    segs = pkg_full.split("_")
    if len(segs) < 5:  # Name_Version_Arch_ResourceId_PublisherId
        return None
    family = f"{segs[0]}_{segs[-1]}"
    rel = "\\".join(parts[idx + 2:]).lower()
    manifest = os.path.join(os.sep.join(parts[: idx + 2]), "AppxManifest.xml")
    app_id = None
    try:
        with open(manifest, "r", encoding="utf-8", errors="ignore") as f:
            xml = f.read()
        apps = []
        for tag in re.findall(r"<Application\b[^>]*>", xml):
            m_id = re.search(r'\bId="([^"]+)"', tag)
            m_exe = re.search(r'\bExecutable="([^"]+)"', tag)
            if m_id:
                apps.append((m_id.group(1), (m_exe.group(1) if m_exe else "").replace("/", "\\").lower()))
        for aid, exe in apps:
            if exe and exe == rel:
                app_id = aid
                break
        if app_id is None and apps:
            app_id = apps[0][0]
    except OSError:
        pass
    if app_id is None:
        return None
    return f"{family}!{app_id}"


def _windowsapps_family(path: str):
    parts = os.path.normpath(path).split(os.sep)
    low = [p.lower() for p in parts]
    if "windowsapps" not in low:
        return None
    idx = low.index("windowsapps")
    if idx + 1 >= len(parts):
        return None
    segs = parts[idx + 1].split("_")
    if len(segs) < 5:
        return None
    return f"{segs[0]}_{segs[-1]}"


# ----------------------------------------------------------------------------
# Installed Start-menu apps (AUMID list) - cached, last-resort lookup
# ----------------------------------------------------------------------------
_START_APPS_CACHE = {"ts": 0.0, "apps": []}


def _get_start_apps():
    now = time.time()
    if _START_APPS_CACHE["apps"] and now - _START_APPS_CACHE["ts"] < 600:
        return _START_APPS_CACHE["apps"]
    apps = []
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout.strip()
        data = json.loads(out) if out else []
        if isinstance(data, dict):
            data = [data]
        apps = [(str(d.get("Name", "")), str(d.get("AppID", ""))) for d in data if d.get("AppID")]
    except Exception as e:
        _log(f"Get-StartApps failed: {e}")
    _START_APPS_CACHE.update(ts=now, apps=apps)
    return apps


def _find_start_app(name: str = "", family: str = ""):
    name_l = (name or "").lower().strip()
    family_l = (family or "").lower()
    apps = _get_start_apps()
    if family_l:
        for disp, aid in apps:
            if aid.lower().startswith(family_l + "!"):
                return aid
    if name_l:
        for disp, aid in apps:
            if disp.lower() == name_l:
                return aid
        partial = [aid for disp, aid in apps if name_l in disp.lower()]
        if len(partial) >= 1:
            return partial[0]
    return None


# ----------------------------------------------------------------------------
# Name / path resolution
# ----------------------------------------------------------------------------
_APP_ALIASES = {
    "vs code": "code", "visual studio code": "code", "vscode": "code",
    "word": "winword", "microsoft word": "winword", "powerpoint": "powerpnt",
    "google chrome": "chrome", "edge": "msedge", "microsoft edge": "msedge",
    "calculator": "calc", "file explorer": "explorer", "files": "explorer",
    "terminal": "wt", "windows terminal": "wt", "obs": "obs64", "obs studio": "obs64",
    "settings": "ms-settings:", "whatsapp": "whatsapp:",
}


def _known_install_candidates(key: str):
    la = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    table = {
        "code": [os.path.join(la, "Programs", "Microsoft VS Code", "Code.exe"),
                 os.path.join(pf, "Microsoft VS Code", "Code.exe")],
        "spotify": [os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
                    os.path.join(la, "Spotify", "Spotify.exe")],
        "discord": [os.path.join(la, "Discord", "Update.exe")],
        "brave": [os.path.join(la, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                  os.path.join(pf, "BraveSoftware", "Brave-Browser", "Application", "brave.exe")],
        "chrome": [os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
                   os.path.join(la, "Google", "Chrome", "Application", "chrome.exe")],
        "steam": [os.path.join(pf86, "Steam", "steam.exe")],
        "obs64": [os.path.join(pf, "obs-studio", "bin", "64bit", "obs64.exe")],
        "vlc": [os.path.join(pf, "VideoLAN", "VLC", "vlc.exe")],
    }
    return [c for c in table.get(key, []) if c and os.path.exists(c)]


def _registry_app_path(exe_name: str):
    try:
        import winreg
    except ImportError:
        return None
    if not exe_name.lower().endswith(".exe"):
        exe_name += ".exe"
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}") as k:
                val, _ = winreg.QueryValueEx(k, "")
                clean = os.path.expandvars(str(val).strip().strip('"'))
                if clean and os.path.exists(clean):
                    return clean
        except OSError:
            pass
    return None


def _start_menu_shortcut(name: str):
    name_l = name.lower()
    dirs = [
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
        os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop"),
    ]
    partial = None
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                fl = f.lower()
                if not (fl.endswith(".lnk") or fl.endswith(".url")):
                    continue
                stem = fl.rsplit(".", 1)[0]
                if stem == name_l:
                    return os.path.join(root, f)
                if partial is None and name_l in stem and "uninstall" not in stem:
                    partial = os.path.join(root, f)
    return partial


def _resolve_by_name(name: str):
    raw = name.strip().strip('"')
    low = raw.lower()
    stem = low[:-4] if low.endswith(".exe") else low
    key = _APP_ALIASES.get(low, _APP_ALIASES.get(stem, stem))
    if _is_uri(key):
        return key

    # 1. Known install locations (prefer real .exe over .cmd shims such as code.cmd)
    known = _known_install_candidates(key)
    if known:
        return known[0]
    # 2. App Paths registry
    reg = _registry_app_path(key)
    if reg:
        return reg
    # 3. PATH (skip .cmd/.bat shims and 0-byte WindowsApps stubs when possible)
    found = shutil.which(key) or shutil.which(stem)
    is_winapps_alias = bool(found and r"\microsoft\windowsapps" in found.lower())
    if found and not found.lower().endswith((".cmd", ".bat")) and not is_winapps_alias:
        return found
    # 4. Start menu / desktop shortcuts
    lnk = _start_menu_shortcut(raw if not low.endswith(".exe") else raw[:-4])
    if lnk:
        return lnk
    # 5. Installed Start apps (covers Store apps such as WhatsApp, Spotify Store, Xbox ...)
    aumid = _find_start_app(name=raw if not low.endswith(".exe") else raw[:-4])
    if aumid:
        return APPS_FOLDER_PREFIX + aumid
    if found:
        return found
    # 6. Let ShellExecute try the bare name (raises a real OSError if it doesn't exist)
    if re.fullmatch(r"[\w .+\-]+", key) and not os.path.isabs(key):
        return key
    return None


_VERSION_DIR_RE = re.compile(r"^(app-[\d.]+|version-[0-9a-f]+|\d+(\.\d+){1,3})$", re.IGNORECASE)


def _heal_missing_path(path: str):
    """Find the updated location of an app whose stored path no longer exists."""
    norm = os.path.normpath(path)
    # a) Updated Store package -> AUMID via installed start apps
    fam = _windowsapps_family(norm)
    if fam:
        aid = _find_start_app(family=fam)
        if aid:
            return APPS_FOLDER_PREFIX + aid
    # b) Versioned folder (Squirrel app-1.2.3, Roblox version-abc, Chrome 120.0.1.2 ...)
    parts = norm.split(os.sep)
    for i in range(len(parts) - 1, 0, -1):
        if _VERSION_DIR_RE.match(parts[i]):
            prefix = parts[i].split("-")[0] + "-*" if "-" in parts[i] else "*"
            pattern = os.sep.join(parts[:i] + [prefix] + parts[i + 1:])
            matches = [m for m in glob.glob(pattern) if os.path.exists(m)]
            if matches:
                matches.sort(key=lambda m: os.path.getmtime(m), reverse=True)
                return matches[0]
    # c) Resolve again by the app's name
    return _resolve_by_name(display_name(norm))


def resolve_launch_target(app):
    """Turn a stored workspace entry into something launchable (or None)."""
    raw = str(app or "").strip().strip('"')
    if not raw:
        return None
    if raw.lower().startswith("shell:"):
        return raw
    looks_like_path = bool(re.match(r"^[a-zA-Z]:[\\/]", raw)) or raw.startswith("\\\\")
    if _is_uri(raw) and not looks_like_path:
        return raw
    if looks_like_path:
        expanded = os.path.expandvars(raw)
        if os.path.exists(expanded):
            aumid = _aumid_from_windowsapps_path(expanded)
            if aumid:
                return APPS_FOLDER_PREFIX + aumid
            return expanded
        return _heal_missing_path(expanded)
    return _resolve_by_name(raw)


def normalize_app_token(app) -> str:
    """Canonical form stored in the workspace file."""
    s = str(app or "").strip().strip('"')
    if not s:
        return ""
    if re.match(r"^[a-zA-Z]:[\\/]", s) and os.path.exists(s):
        aumid = _aumid_from_windowsapps_path(s)
        if aumid:
            return APPS_FOLDER_PREFIX + aumid
        return os.path.normpath(s)
    return s


def _start_target(target: str):
    low = target.lower()
    if low.startswith("shell:"):
        subprocess.Popen(["explorer.exe", target], creationflags=subprocess.CREATE_NO_WINDOW)
        return
    if re.match(r"^[a-zA-Z]:[\\/]", target) or target.startswith("\\\\"):
        target = os.path.normpath(target)
        low = target.lower()
    if low.endswith("\\discord\\update.exe"):
        subprocess.Popen([target, "--processStart", "Discord.exe"], creationflags=subprocess.CREATE_NO_WINDOW)
        return
    if low.endswith((".lnk", ".url")) or r"\microsoft\windowsapps" in low:
        os.startfile(target)
        return
    if os.path.isabs(target) and os.path.isfile(target):
        # Launch with the app's own folder as working dir (many games / tools require this)
        os.startfile(target, cwd=os.path.dirname(target))
        return
    os.startfile(target)  # URIs, App Paths names, etc. Raises OSError if not found.


def launch_app(app):
    raw = str(app or "").strip()
    if not raw:
        return {"success": False, "reason": "Empty app name.", "app": raw}
    # If the user asked to launch a saved workspace (e.g. "power workspace" or a workspace name),
    # check workspaces first when "workspace" is mentioned.
    if "workspace" in raw.lower():
        ws = load_workspaces()
        matched_ws = match_workspace_name(raw, ws)
        if matched_ws:
            return manage_workspace("launch", matched_ws)
    try:
        target = resolve_launch_target(raw)
    except Exception as e:
        target = None
        _log(f"resolve error for {raw!r}: {e}")
    if not target:
        ws = load_workspaces()
        matched_ws = match_workspace_name(raw, ws)
        if matched_ws:
            return manage_workspace("launch", matched_ws)
        return {"success": False, "reason": f"Could not find '{display_name(raw)}' on this PC.", "app": raw}
    try:
        _start_target(target)
        _log(f"launched {raw!r} -> {target!r}")
        return {"success": True, "reason": f"Launched {display_name(raw)}.", "app": raw, "target": target}
    except OSError as e:
        ws = load_workspaces()
        matched_ws = match_workspace_name(raw, ws)
        if matched_ws:
            return manage_workspace("launch", matched_ws)
        _log(f"launch failed {raw!r} -> {target!r}: {e}")
        return {"success": False, "reason": f"Failed to start '{display_name(raw)}': {e.strerror or e}", "app": raw,
                "target": target}
    except Exception as e:
        _log(f"launch failed {raw!r} -> {target!r}: {e}")
        return {"success": False, "reason": f"Failed to start '{display_name(raw)}': {e}", "app": raw, "target": target}


# ----------------------------------------------------------------------------
# True open-window capture
# ----------------------------------------------------------------------------
def capture_active_windows():
    import psutil

    my_pid = os.getpid()
    apps, details, seen = [], [], set()

    com_hr = _ole32.CoInitializeEx(None, 0x2)  # COINIT_APARTMENTTHREADED (S_FALSE if already)

    def _uwp_child_aumid(parent_hwnd, host_pid):
        found = [None]

        def _child_cb(ch, _lp):
            cpid = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(ch, ctypes.byref(cpid))
            if cpid.value and cpid.value != host_pid:
                found[0] = cpid.value
                return False
            return True

        cb = WNDENUMPROC(_child_cb)
        _user32.EnumChildWindows(parent_hwnd, cb, 0)
        return _process_aumid(found[0]) if found[0] else None

    def _add(token, title):
        key = token.lower()
        if key in seen:
            return
        seen.add(key)
        apps.append(token)
        details.append({"name": display_name(token), "title": title, "app": token})

    def _enum_cb(hwnd, _lp):
        try:
            if not _user32.IsWindowVisible(hwnd):
                return True
            cloaked = ctypes.c_int(0)
            _dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
            if cloaked.value:
                return True
            ex = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            app_window = bool(ex & WS_EX_APPWINDOW)
            if (ex & WS_EX_TOOLWINDOW) and not app_window:
                return True
            if (ex & WS_EX_NOACTIVATE) and not app_window:
                return True
            if _user32.GetWindow(hwnd, GW_OWNER) and not app_window:
                return True  # owned popups / dialogs are not taskbar apps
            if not _user32.IsIconic(hwnd):
                rc = wintypes.RECT()
                if _user32.GetWindowRect(hwnd, ctypes.byref(rc)):
                    if (rc.right - rc.left) < 80 or (rc.bottom - rc.top) < 40:
                        return True
            length = _user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            tbuf = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, tbuf, length + 1)
            title = tbuf.value.strip()
            if not title or title.lower() in _SKIP_TITLES:
                return True
            cbuf = ctypes.create_unicode_buffer(256)
            _user32.GetClassNameW(hwnd, cbuf, 256)
            cls = cbuf.value
            if cls in _SKIP_CLASSES:
                return True

            pid = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_id = pid.value
            if not proc_id or proc_id == my_pid:
                return True

            exe = ""
            try:
                exe = psutil.Process(proc_id).exe()
            except Exception:
                exe = _process_image_path(proc_id)
            if not exe:
                return True
            name_l = os.path.basename(exe).lower()
            if name_l in _SKIP_EXES:
                return True

            if name_l == "applicationframehost.exe":
                aumid = _window_aumid(hwnd) or _uwp_child_aumid(hwnd, proc_id)
                if aumid:
                    _add(APPS_FOLDER_PREFIX + aumid, title)
                return True

            if name_l == "explorer.exe":
                if cls == "CabinetWClass":
                    _add("explorer", title)
                return True

            aumid = _process_aumid(proc_id)
            if aumid:
                _add(APPS_FOLDER_PREFIX + aumid, title)
            else:
                _add(exe, title)
        except Exception:
            pass
        return True

    try:
        cb_ref = WNDENUMPROC(_enum_cb)
        _user32.EnumWindows(cb_ref, 0)
        return {"success": True, "apps": apps, "details": details}
    except Exception as e:
        return {"success": False, "reason": str(e), "apps": [], "details": []}
    finally:
        if com_hr in (0, 1):  # S_OK / S_FALSE must be balanced
            _ole32.CoUninitialize()


# ----------------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------------
def normalize_ws_apps(entry):
    if isinstance(entry, dict):
        raw = entry.get("apps", [])
    elif isinstance(entry, list):
        raw = entry
    elif isinstance(entry, str):
        raw = [entry]
    else:
        raw = []
    out, seen = [], set()
    for item in raw:
        if isinstance(item, str) and item.strip():
            s = item.strip()
            if s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
    return out


def load_workspaces():
    with _LOCK:
        if not os.path.exists(WS_FILE):
            return {}
        try:
            with open(WS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            _log(f"could not read {WS_FILE}: {e}")
            return {}
        if not isinstance(data, dict):
            return {}
        out = {}
        for k, v in data.items():
            key = str(k).strip().lower()
            if key:
                out[key] = normalize_ws_apps(v)
        return out


def save_workspaces(workspaces):
    with _LOCK:
        tmp = WS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(workspaces, f, indent=2)
        os.replace(tmp, WS_FILE)  # atomic: never leaves a half-written file


_NAME_NOISE = re.compile(r"\b(the|my|a|workspace|workspaces|work\s*space|mode|setup|profile|apps?)\b", re.I)


def _clean_ws_name(name):
    return " ".join(_NAME_NOISE.sub(" ", str(name or "").lower()).split())


def match_workspace_name(name, workspaces):
    n = str(name or "").strip().lower()
    if not n:
        return None
    if n in workspaces:
        return n
    cleaned = _clean_ws_name(n)
    if cleaned in workspaces:
        return cleaned
    for k in workspaces:
        if _clean_ws_name(k) == cleaned and cleaned:
            return k
    if cleaned:
        cands = [k for k in workspaces if cleaned in k or (k and k in cleaned)]
        if len(cands) == 1:
            return cands[0]
    return None


def _remove_matches(apps, remove_apps):
    rem = {str(r).strip().lower() for r in (remove_apps or []) if str(r).strip()}
    if not rem:
        return apps
    kept = []
    for a in apps:
        keys = {a.lower(), os.path.basename(a).lower(), display_name(a).lower()}
        keys.add(os.path.basename(a).lower().replace(".exe", ""))
        if keys & rem:
            continue
        kept.append(a)
    return kept


def manage_workspace(action, name, apps=None, remove_apps=None):
    action = str(action or "").lower().strip()
    with _LOCK:
        workspaces = load_workspaces()

        if action == "list":
            return {"success": True, "workspaces": workspaces}

        raw_name = str(name or "").strip()
        if not raw_name:
            return {"success": False, "reason": "Workspace name cannot be empty."}

        if action in ("create", "save"):
            key = _clean_ws_name(raw_name) or raw_name.lower()
            clean = normalize_ws_apps([normalize_app_token(a) for a in (apps or [])])
            workspaces[key] = clean
            save_workspaces(workspaces)
            return {"success": True, "name": key, "apps": clean,
                    "reason": f"Workspace '{key}' saved with {len(clean)} apps."}

        key = match_workspace_name(raw_name, workspaces)

        if action == "edit":
            if key is None:
                key = _clean_ws_name(raw_name) or raw_name.lower()
                workspaces[key] = []
            current = list(workspaces.get(key, []))
            for a in apps or []:
                tok = normalize_app_token(a)
                if tok and tok.lower() not in {c.lower() for c in current}:
                    current.append(tok)
            current = _remove_matches(current, remove_apps)
            workspaces[key] = current
            save_workspaces(workspaces)
            return {"success": True, "name": key, "apps": current, "reason": f"Workspace '{key}' updated."}

        if key is None:
            known = ", ".join(sorted(workspaces)) or "none saved yet"
            return {"success": False, "reason": f"Workspace '{raw_name}' not found (saved: {known})."}

        if action == "delete":
            del workspaces[key]
            save_workspaces(workspaces)
            return {"success": True, "name": key, "reason": f"Workspace '{key}' deleted."}

        if action == "get":
            return {"success": True, "name": key, "apps": workspaces[key]}

        if action == "launch":
            to_launch = workspaces[key]
            if not to_launch:
                return {"success": False, "name": key, "launched": [], "failed": [],
                        "reason": f"Workspace '{key}' has no apps. Edit it and add some first."}
    # Launch outside the lock so slow apps never block other workspace operations
    if action == "launch":
        launched, failed = [], []
        for app in to_launch:
            res = launch_app(app)
            if res.get("success"):
                launched.append(display_name(app))
            else:
                failed.append({"app": display_name(app), "reason": res.get("reason", "")})
            time.sleep(0.12)
        ok = len(launched) > 0
        reason = f"Launched {len(launched)}/{len(to_launch)} apps in '{key}'."
        if failed:
            reason += " Failed: " + ", ".join(f["app"] for f in failed) + "."
        return {"success": ok, "name": key, "launched": launched, "failed": failed, "reason": reason}

    return {"success": False, "reason": f"Invalid workspace action '{action}'."}


def launch_workspace_async(name, callback=None):
    """Launch on a daemon thread; ``callback(result_dict)`` is called from that thread."""
    def _run():
        try:
            res = manage_workspace("launch", name)
        except Exception as e:
            res = {"success": False, "reason": str(e), "launched": [], "failed": []}
        if callback:
            try:
                callback(res)
            except Exception:
                pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
