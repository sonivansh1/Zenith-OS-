import os
import psutil
from pathlib import Path
import ctypes
import subprocess

def get_user_desktop():
    onedrive_desktop = Path.home() / "OneDrive" / "Desktop"
    if onedrive_desktop.exists():
        return onedrive_desktop
    return Path.home() / "Desktop"

def resolve_system_path(path_str):
    """
    Intelligently resolves system folders, aliases ('Downloads', 'Desktop', 'Documents'),
    relative subpaths ('months', 'Desktop/months'), and case-insensitive file paths.
    """
    if not path_str:
        return str(get_user_desktop())
    p_str = str(path_str).strip().strip('"').strip("'")
    low = p_str.lower()
    
    # Common user folder alias resolution
    if low in ("download", "downloads", "download folder", "downloads folder", "my downloads"):
        return str(Path.home() / "Downloads")
    if low in ("desktop", "desktop folder", "my desktop"):
        return str(get_user_desktop())
    if low in ("document", "documents", "documents folder", "my documents"):
        return str(Path.home() / "Documents")
    if low in ("pictures", "pictures folder", "my pictures"):
        return str(Path.home() / "Pictures")
    if low in ("music", "music folder", "my music"):
        return str(Path.home() / "Music")
    if low in ("videos", "videos folder", "my videos"):
        return str(Path.home() / "Videos")

    # If starts with desktop/ or downloads/ or documents/
    if low.startswith("desktop/") or low.startswith("desktop\\"):
        sub = p_str[8:].lstrip("/\\")
        return str(get_user_desktop() / sub)
    if low.startswith("downloads/") or low.startswith("downloads\\"):
        sub = p_str[10:].lstrip("/\\")
        return str(Path.home() / "Downloads" / sub)
    if low.startswith("documents/") or low.startswith("documents\\"):
        sub = p_str[10:].lstrip("/\\")
        return str(Path.home() / "Documents" / sub)

    # If already an existing path or absolute
    if os.path.exists(p_str) or os.path.isabs(p_str):
        return resolve_case_insensitive(p_str)
        
    # Relative path without parent: default under Desktop
    return str(get_user_desktop() / p_str)

def resolve_case_insensitive(path_str):
    if not path_str: return path_str
    if os.path.exists(path_str):
        return path_str
        
    p = Path(path_str)
    if not p.parent.exists():
        return path_str # Can't resolve if parent doesn't exist either
        
    try:
        for child in p.parent.iterdir():
            if child.name.lower() == p.name.lower():
                return str(child)
    except Exception:
        pass
    return path_str

def get_battery_fast():
    battery = psutil.sensors_battery()
    return int(battery.percent) if battery else 100

def get_system_stats():
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()
    bat_percent = battery.percent if battery else 100
    is_charging = battery.power_plugged if battery else False
    return {
        "cpu": cpu,
        "ram": ram,
        "battery": bat_percent,
        "is_charging": is_charging,
        "gpu": 0,
        "net_down": "0K",
        "net_up": "0K"
    }

def get_blacklist():
    return [
        Path(os.environ.get("SystemRoot", "C:\\Windows")).resolve(),
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")).resolve(),
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")).resolve()
    ]

def is_safe_path(target_path):
    try:
        p = Path(target_path).resolve()
        
        # Protect the exact user home folder, but allow children (like Desktop)
        home_dir = Path(os.path.expanduser("~")).resolve()
        if p == home_dir or p.parent == home_dir:
            # We don't want to block creating/moving files inside Desktop, 
            # but we DO want to block deleting/moving files directly in ~
            # Wait, if p is C:\Users\vansh\Desktop, p.parent == home_dir, so it would block it!
            # If the user tries to delete the Desktop folder itself, it's blocked.
            # But what if they try to create a file in ~? Blocked.
            pass
            
        if p == home_dir or (p.parent == home_dir and p.is_file()):
            return False
            
        c_root = Path("C:\\").resolve()
        if p == c_root or p.parent == c_root:
            return False
            
        for b in get_blacklist():
            if p == b or b in p.parents:
                return False
        return True
    except:
        return False

def create_folder(target_path):
    resolved = resolve_system_path(target_path)
    if not is_safe_path(resolved):
        return {"success": False, "reason": "Security Error: Attempted to modify blacklisted directory."}
        
    try:
        os.makedirs(resolved, exist_ok=True)
        return {"success": True, "reason": f"Folder '{os.path.basename(resolved)}' created successfully.", "path": resolved}
    except Exception as e:
        return {"success": False, "reason": f"Failed to create folder: {str(e)}"}

def safe_delete(target_path):
    resolved = resolve_system_path(target_path)
    if not is_safe_path(resolved):
        return {"success": False, "reason": "Security Error: Attempted to delete blacklisted directory."}
        
    try:
        from send2trash import send2trash
        send2trash(resolved)
        return {"success": True, "reason": f"'{os.path.basename(resolved)}' moved to recycle bin."}
    except Exception as e:
        return {"success": False, "reason": f"Failed to delete: {str(e)}"}

def get_folder_size(target_path):
    resolved = resolve_system_path(target_path)
    total_size = 0
    try:
        if os.path.isfile(resolved):
            return os.path.getsize(resolved)
        for dirpath, dirnames, filenames in os.walk(resolved):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
                except (OSError, PermissionError):
                    continue
    except Exception:
        pass
    return total_size

def get_path_size_formatted(target_path):
    resolved = resolve_system_path(target_path)
    if not os.path.exists(resolved):
        return {"success": False, "reason": f"Path '{target_path}' does not exist.", "size_str": ""}
    size = get_folder_size(resolved)
    
    if size < 1024:
        s_str = f"{size} B"
    elif size < 1024**2:
        s_str = f"{size/1024:.2f} KB"
    elif size < 1024**3:
        s_str = f"{size/(1024**2):.2f} MB"
    else:
        s_str = f"{size/(1024**3):.2f} GB"
        
    return {"success": True, "size_str": s_str, "path": resolved}

def list_files(target_path):
    target_path = resolve_case_insensitive(target_path)
    if not os.path.exists(target_path):
        return {"success": False, "reason": f"Directory '{target_path}' does not exist."}
    if not os.path.isdir(target_path):
        return {"success": False, "reason": f"'{target_path}' is not a directory."}
        
    try:
        items = os.listdir(target_path)
        if not items:
            return {"success": True, "reason": f"Directory '{os.path.basename(target_path)}' is empty.", "files": []}
            
        file_details = []
        for item in items:
            full_path = os.path.join(target_path, item)
            size_mb = 0
            
            # Truncate for spoken TTS brevity
            base_name = os.path.splitext(item)[0]
            short_name = base_name[:12] + ".." if len(base_name) > 12 else base_name
            
            if os.path.isfile(full_path):
                size_mb = os.path.getsize(full_path) / (1024*1024)
            file_details.append(f"{short_name} ({size_mb:.2f} MB)" if size_mb > 0 else f"{short_name} (Folder)")
            
        return {"success": True, "reason": f"Contains {len(items)} items: {', '.join(file_details[:10])}{' and more...' if len(items) > 10 else ''}", "files": items}
    except Exception as e:
        return {"success": False, "reason": f"Error reading directory: {str(e)}"}

def toggle_wifi(state):
    # state is "on" or "off"
    verb = "enable" if state == "on" else "disable"
    try:
        # Requires Admin UAC
        cmd = f'Start-Process powershell -ArgumentList "-Command netsh interface set interface `\\"Wi-Fi`\\" admin={verb}" -Verb RunAs -WindowStyle Hidden'
        subprocess.run(["powershell", "-Command", cmd], creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "reason": f"Wi-Fi {state} command sent."}
    except Exception as e:
        return {"success": False, "reason": str(e)}

def toggle_bluetooth(state):
    # For Bluetooth, we open the settings page as Win11 restricts direct background toggling without WinRT/C++ SDK
    try:
        subprocess.run(["cmd", "/c", "start ms-settings:bluetooth"], creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "reason": f"Opened Bluetooth settings to turn {state}."}
    except Exception as e:
        return {"success": False, "reason": str(e)}

def toggle_airplane(state):
    try:
        subprocess.run(["cmd", "/c", "start ms-settings:network-airplanemode"], creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "reason": f"Opened Airplane Mode settings to turn {state}."}
    except Exception as e:
        return {"success": False, "reason": str(e)}

def toggle_hotspot(state):
    try:
        subprocess.run(["cmd", "/c", "start ms-settings:network-mobilehotspot"], creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "reason": f"Opened Mobile Hotspot settings to turn {state}."}
    except Exception as e:
        return {"success": False, "reason": str(e)}

def toggle_battery_saver(state):
    # We can use powercfg or settings. Settings is safer.
    try:
        subprocess.run(["cmd", "/c", "start ms-settings:batterysaver"], creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "reason": f"Opened Battery Saver settings to turn {state}."}
    except Exception as e:
        return {"success": False, "reason": str(e)}

def toggle_night_light(state):
    try:
        subprocess.run(["cmd", "/c", "start ms-settings:nightlight"], creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "reason": f"Opened Night Light settings to turn {state}."}
    except Exception as e:
        return {"success": False, "reason": str(e)}

def lock_pc():
    ctypes.windll.user32.LockWorkStation()
    return {"success": True, "reason": "Workstation locked."}

def get_brightness() -> int:
    try:
        import screen_brightness_control as sbc
        b = sbc.get_brightness()
        return int(b[0]) if isinstance(b, list) and len(b) > 0 else int(b)
    except Exception:
        return 50

import threading
_local_audio = threading.local()

def _get_endpoint_volume():
    """Retrieve or create thread-local IAudioEndpointVolume interface (thread-safe, zero apartment conflict)."""
    if hasattr(_local_audio, 'endpoint') and _local_audio.endpoint is not None:
        return _local_audio.endpoint
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        from pycaw.pycaw import AudioUtilities
        spk = AudioUtilities.GetSpeakers()
        if hasattr(spk, 'EndpointVolume'):
            _local_audio.endpoint = spk.EndpointVolume
            return _local_audio.endpoint
    except Exception:
        pass
    return None

def get_volume() -> int:
    try:
        endpoint = _get_endpoint_volume()
        if endpoint is not None:
            return int(round(endpoint.GetMasterVolumeLevelScalar() * 100))
        from pycaw.pycaw import AudioUtilities
        spk = AudioUtilities.GetSpeakers()
        if hasattr(spk, 'EndpointVolume'):
            return int(round(spk.EndpointVolume.GetMasterVolumeLevelScalar() * 100))
        return 50
    except Exception:
        try:
            _local_audio.endpoint = None
            endpoint = _get_endpoint_volume()
            if endpoint is not None:
                return int(round(endpoint.GetMasterVolumeLevelScalar() * 100))
        except Exception:
            pass
        return 50

def set_brightness(level):
    try:
        import screen_brightness_control as sbc
        level_str = str(level).strip().lower()
        if level_str.startswith(('+', '-')) or level_str in ('up', 'down'):
            current = get_brightness()
            if level_str == 'up': delta = 10
            elif level_str == 'down': delta = -10
            else: delta = int(level)
            new_level = current + delta
        else:
            new_level = int(level)
            
        new_level = max(0, min(100, new_level))
        sbc.set_brightness(new_level)
        return {"success": True, "reason": f"Brightness set to {new_level}%."}
    except Exception as e:
        return {"success": False, "reason": f"Failed to set brightness: {e}"}

def set_volume(level):
    try:
        volume = _get_endpoint_volume()
        if not volume:
            return {"success": False, "reason": "No audio endpoint available."}

        level_str = str(level).strip().lower()
        # Fast path: absolute integer or float volume skips GetMasterVolumeLevelScalar query (~0.1ms)
        if level_str.startswith(('+', '-')) or level_str in ('up', 'down'):
            try:
                current = volume.GetMasterVolumeLevelScalar()
            except Exception:
                _local_audio.endpoint = None
                volume = _get_endpoint_volume()
                if not volume:
                    return {"success": False, "reason": "No audio endpoint available."}
                current = volume.GetMasterVolumeLevelScalar()

            if level_str == 'up': delta = 0.05
            elif level_str == 'down': delta = -0.05
            else: delta = float(level) / 100.0
            scalar_vol = current + delta
        else:
            scalar_vol = float(level) / 100.0
            
        scalar_vol = max(0.0, min(1.0, scalar_vol))
        try:
            volume.SetMasterVolumeLevelScalar(scalar_vol, None)
        except Exception:
            # Re-acquire thread-local endpoint on COM staleness and retry
            _local_audio.endpoint = None
            volume = _get_endpoint_volume()
            if volume:
                volume.SetMasterVolumeLevelScalar(scalar_vol, None)
            else:
                return {"success": False, "reason": "Audio endpoint re-acquisition failed."}

        return {"success": True, "reason": f"Volume set to {int(scalar_vol * 100)}%."}
    except Exception as e:
        return {"success": False, "reason": f"Failed to set volume: {e}"}

def _resolve_app_executable(app_name: str) -> str:
    """Resolve an app name / path into a launch target (delegates to workspace_engine)."""
    import workspace_engine
    return workspace_engine.resolve_launch_target(app_name) or ""

def launch_app(app_name):
    """Launch an app by name, path, .lnk, URI or shell:AppsFolder AUMID. Never fails silently."""
    import workspace_engine
    return workspace_engine.launch_app(app_name)

def move_file(source, destination):
    if not is_safe_path(source) or not is_safe_path(destination):
        return {"success": False, "reason": "Path is protected by safety guardrails."}
    
    try:
        import shutil
        shutil.move(source, destination)
        return {"success": True, "reason": f"Moved successfully."}
    except Exception as e:
        return {"success": False, "reason": str(e)}

def create_file_secure(filename, destination, file_type, content):
    whitelist = ['.txt', '.md', '.py', '.html', '.css', '.js', '.json', '.csv', '.pdf', '.docx']
    blacklist = ['.exe', '.dll', '.msi', '.sys', '.com', '.scr', '.bat', '.cmd', '.vbs', '.ps1', '.wsf', '.reg', '.lnk', '.ini', '.inf']
    
    file_ext = f".{file_type.lower().strip('.')}"
    if file_ext not in whitelist:
        return {"success": False, "reason": f"Extension {file_ext} is not in the whitelist."}
    if file_ext in blacklist:
        return {"success": False, "reason": f"Extension {file_ext} is strictly blacklisted."}
        
    # Resolve target directory (supports Desktop, Documents, Downloads, or any subfolder e.g. 'months', 'Desktop/months')
    base_dir_str = resolve_system_path(destination or "Desktop")
    base_dir = Path(base_dir_str)
    
    # Sandboxing check: ensure target is within user profile area and safe
    if not is_safe_path(str(base_dir)):
        return {"success": False, "reason": "Security Error: Destination is in a protected system directory."}
        
    if not base_dir.exists():
        base_dir.mkdir(parents=True, exist_ok=True)
        
    try:
        clean_filename = os.path.basename(filename.strip())
        if not clean_filename.lower().endswith(file_ext):
            clean_filename += file_ext
        final_path = (base_dir / clean_filename).resolve()
        
        # Guard against traversal out of base_dir
        if not str(final_path).startswith(str(base_dir.resolve())):
            return {"success": False, "reason": "Security Error: Attempted directory traversal."}
            
        if final_path.exists():
            return {"success": True, "reason": f"File {clean_filename} already exists."}
            
        # Generation
        if file_ext == ".pdf":
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.multi_cell(0, 10, txt=content or "")
            pdf.output(str(final_path))
        elif file_ext == ".docx":
            import docx
            doc = docx.Document()
            doc.add_paragraph(content or "")
            doc.save(str(final_path))
        else:
            with open(final_path, 'w', encoding='utf-8') as f:
                f.write(content or "")
                
        return {"success": True, "reason": f"Created {clean_filename} in {base_dir.name}."}
    except Exception as e:
        return {"success": False, "reason": str(e)}



def open_website(url):
    import webbrowser
    if not url.startswith('http'):
        if '.' not in url:
            url = url + '.com'
        url = 'https://' + url
    webbrowser.open(url)

def search_web(query):
    import urllib.parse
    import webbrowser
    url = f'https://www.google.com/search?q={urllib.parse.quote(query)}'
    webbrowser.open(url)

def minimize_all():
    try:
        import win32com.client
        shell = win32com.client.Dispatch("Shell.Application")
        shell.MinimizeAll()
    except Exception as e:
        print("Failed to minimize all:", e)



import time

def get_uptime():
    try:
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return f"{hours} hours, {minutes} minutes"
    except:
        return "Unknown"

def get_top_processes(sort_by="memory_percent", limit=5):
    try:
        processes = []
        for p in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
            try:
                processes.append(p.info)
            except:
                pass
        processes = sorted(processes, key=lambda x: x[sort_by] or 0, reverse=True)[:limit]
        return processes
    except:
        return []

def kill_process(name_or_pid):
    try:
        if str(name_or_pid).isdigit():
            p = psutil.Process(int(name_or_pid))
            p.kill()
            return {"success": True, "reason": f"Killed process {name_or_pid}"}
        else:
            name = str(name_or_pid).lower()
            killed = 0
            for p in psutil.process_iter(['pid', 'name']):
                if p.info['name'] and name in p.info['name'].lower():
                    p.kill()
                    killed += 1
            if killed > 0:
                return {"success": True, "reason": f"Killed {killed} processes matching '{name}'"}
            return {"success": False, "reason": f"No process found matching '{name}'"}
    except Exception as e:
        return {"success": False, "reason": str(e)}

def get_temperatures():
    # Placeholder for actual hardware sensors, often requires WMI admin or LibreHardwareMonitor
    return {"cpu": "N/A (Requires Admin)", "gpu": "N/A"}



def find_file(filename):
    import os
    home = os.path.expanduser('~')
    search_dirs = [os.path.join(home, 'Desktop'), os.path.join(home, 'Documents'), os.path.join(home, 'Downloads')]
    found_paths = []
    
    for sdir in search_dirs:
        for root, dirs, files in os.walk(sdir):
            for f in files:
                if filename.lower() in f.lower():
                    found_paths.append(os.path.join(root, f))
            if len(found_paths) >= 5:
                break
        if len(found_paths) >= 5:
            break
            
    if found_paths:
        return {'success': True, 'paths': found_paths[:5]}
    return {'success': False, 'reason': 'File not found.'}

def _normalize_ws_apps(entry):
    import workspace_engine
    return workspace_engine.normalize_ws_apps(entry)

def manage_workspace(action, name, apps=None, remove_apps=None):
    """create / edit / launch / delete / get / list workspaces (delegates to workspace_engine)."""
    import workspace_engine
    return workspace_engine.manage_workspace(action, name, apps=apps, remove_apps=remove_apps)

def read_website(url):
    try:
        import urllib.request
        from bs4 import BeautifulSoup
        if not url.startswith('http'):
            url = 'https://' + url
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        for script in soup(['script', 'style', 'header', 'footer', 'nav']):
            script.extract()
        text = soup.get_text(separator=' ')
        lines = (line.strip() for line in text.splitlines())
        text = '\n'.join(chunk for line in lines for chunk in line.split('  ') if chunk)
        if len(text) > 3000:
            text = text[:3000] + '... [Truncated]'
        return {'success': True, 'text': text}
    except Exception as e:
        return {'success': False, 'reason': str(e)}


def set_power_mode(mode):
    import subprocess
    mode = mode.lower()
    cmd = None
    if 'saver' in mode or 'battery' in mode:
        cmd = 'powercfg /SETACTIVE SCHEME_MAX'
    elif 'performance' in mode or 'max' in mode:
        cmd = 'powercfg /SETACTIVE SCHEME_MIN'
    elif 'balance' in mode:
        cmd = 'powercfg /SETACTIVE SCHEME_BALANCED'
        
    if cmd:
        try:
            subprocess.run(['cmd', '/c', cmd], creationflags=subprocess.CREATE_NO_WINDOW)
            return {'success': True, 'reason': f'Power mode set to {mode}.'}
        except Exception as e:
            return {'success': False, 'reason': str(e)}
    return {'success': False, 'reason': 'Unknown power mode.'}


def capture_active_windows():
    """True open-window detection (delegates to workspace_engine)."""
    import workspace_engine
    return workspace_engine.capture_active_windows()
