import os
import re
import subprocess
import webbrowser
from typing import List, Dict, Any, Optional

# Supported application configurations and aliases
APP_REGISTRY: Dict[str, Dict[str, Any]] = {
    "whatsapp": {
        "name": "WhatsApp",
        "icon": "💬",
        "category": "Communication",
        "web_url": "https://web.whatsapp.com",
        "protocol": "whatsapp://",
        "description": "WhatsApp Messenger (Desktop App & Web)",
        "aliases": ["whatsapp", "whats app", "wa"]
    },
    "chrome": {
        "name": "Google Chrome",
        "icon": "🌐",
        "category": "Browser",
        "web_url": "https://www.google.com",
        "description": "Google Chrome Browser",
        "aliases": ["chrome", "google chrome", "browser"]
    },
    "youtube": {
        "name": "YouTube",
        "icon": "▶️",
        "category": "Media",
        "web_url": "https://www.youtube.com",
        "description": "YouTube Streaming Video",
        "aliases": ["youtube", "yt"]
    },
    "gmail": {
        "name": "Gmail",
        "icon": "📧",
        "category": "Productivity",
        "web_url": "https://mail.google.com",
        "description": "Google Mail",
        "aliases": ["gmail", "google mail", "mail"]
    },
    "github": {
        "name": "GitHub",
        "icon": "🐙",
        "category": "Development",
        "web_url": "https://github.com",
        "description": "GitHub Repository Platform",
        "aliases": ["github", "git hub"]
    },
    "calculator": {
        "name": "Calculator",
        "icon": "🧮",
        "category": "Utilities",
        "command": "calc.exe",
        "description": "Windows Calculator",
        "aliases": ["calculator", "calc"]
    },
    "notepad": {
        "name": "Notepad",
        "icon": "📝",
        "category": "Utilities",
        "command": "notepad.exe",
        "description": "Windows Notepad Editor",
        "aliases": ["notepad", "text editor", "notes"]
    },
    "code": {
        "name": "Visual Studio Code",
        "icon": "💻",
        "category": "Development",
        "command": "code",
        "description": "VS Code IDE",
        "aliases": ["vscode", "vs code", "code editor", "visual studio code"]
    },
    "spotify": {
        "name": "Spotify",
        "icon": "🎵",
        "category": "Media",
        "protocol": "spotify:",
        "web_url": "https://open.spotify.com",
        "description": "Spotify Music Player",
        "aliases": ["spotify", "music"]
    },
    "terminal": {
        "name": "PowerShell Terminal",
        "icon": "⚡",
        "category": "System",
        "command": "powershell.exe",
        "description": "Windows PowerShell Command Prompt",
        "aliases": ["powershell", "terminal", "cmd", "command prompt"]
    },
    "settings": {
        "name": "Windows Settings",
        "icon": "⚙️",
        "category": "System",
        "protocol": "ms-settings:",
        "description": "Windows System Settings",
        "aliases": ["settings", "windows settings", "control panel"]
    },
    "explorer": {
        "name": "File Explorer",
        "icon": "📁",
        "category": "System",
        "command": "explorer.exe",
        "description": "Windows File Explorer",
        "aliases": ["explorer", "file explorer", "files", "my computer"]
    },
    "camera": {
        "name": "Windows Camera",
        "icon": "📷",
        "category": "Media",
        "protocol": "microsoft.windows.camera:",
        "description": "Windows Camera App",
        "aliases": ["camera", "webcam"]
    },
    "paint": {
        "name": "Paint",
        "icon": "🎨",
        "category": "Media",
        "command": "mspaint.exe",
        "description": "MS Paint Drawing Tool",
        "aliases": ["paint", "mspaint", "ms paint"]
    }
}


def get_chrome_executable() -> str:
    """Locates the Google Chrome binary on Windows via registry and common directories."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
        )
        val, _ = winreg.QueryValueEx(key, "")
        if val and os.path.exists(val):
            return val
    except Exception:
        pass

    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "chrome"


def detect_app_launch_intent(message: str) -> List[str]:
    """
    Detects if the user query is asking to open or launch one or more applications/sites.
    Returns a list of matched app keys (e.g. ['whatsapp', 'chrome']).
    """
    msg = message.strip().lower()

    # Trigger verbs that indicate launch request
    triggers = ["open", "launch", "start", "run", "fire up", "bring up"]
    has_trigger = any(re.search(rf"\b{re.escape(t)}\b", msg) for t in triggers)
    if not has_trigger:
        return []

    # Exclude questions like "how to open...", "why open...", "can open...", "open source"
    if "open source" in msg or "open-source" in msg or "open ai" in msg or "openai" in msg:
        return []

    matched_apps: List[str] = []

    # Match each app by its aliases
    for app_key, app_info in APP_REGISTRY.items():
        aliases = app_info.get("aliases", [app_key])
        for alias in aliases:
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, msg):
                if app_key not in matched_apps:
                    matched_apps.append(app_key)
                break

    return matched_apps


def launch_app(app_key: str) -> Dict[str, Any]:
    """
    Executes the app launch on the local Windows OS and returns the launch result details.
    """
    app_info = APP_REGISTRY.get(app_key)
    if not app_info:
        return {
            "app_key": app_key,
            "success": False,
            "error": f"Unknown application: {app_key}"
        }

    name = app_info["name"]
    icon = app_info["icon"]
    chrome_path = get_chrome_executable()

    launched_methods = []
    success = False

    # 1. Custom handling for WhatsApp
    if app_key == "whatsapp":
        # Attempt protocol launch for Desktop WhatsApp
        try:
            os.startfile("whatsapp://")
            launched_methods.append("WhatsApp Desktop Protocol (whatsapp://)")
            success = True
        except Exception:
            pass

        # Also open WhatsApp Web in Chrome to guarantee access
        try:
            if os.path.exists(chrome_path):
                subprocess.Popen([chrome_path, "https://web.whatsapp.com"])
            else:
                subprocess.Popen("start chrome https://web.whatsapp.com", shell=True)
            launched_methods.append("WhatsApp Web (https://web.whatsapp.com)")
            success = True
        except Exception:
            try:
                webbrowser.open("https://web.whatsapp.com")
                launched_methods.append("WhatsApp Web via Default Browser")
                success = True
            except Exception:
                pass

        return {
            "app_key": "whatsapp",
            "name": name,
            "icon": icon,
            "success": success,
            "launched_methods": launched_methods,
            "web_url": "https://web.whatsapp.com",
            "details": "Launched WhatsApp on your Windows desktop and opened WhatsApp Web in Chrome."
        }

    # 2. Custom handling for Google Chrome
    if app_key == "chrome":
        try:
            if os.path.exists(chrome_path):
                subprocess.Popen([chrome_path])
            else:
                subprocess.Popen("start chrome", shell=True)
            success = True
            launched_methods.append(f"Google Chrome Executable ({chrome_path})")
        except Exception as e:
            try:
                subprocess.Popen("cmd /c start chrome", shell=True)
                success = True
                launched_methods.append("Shell Start Command (cmd /c start chrome)")
            except Exception as e2:
                webbrowser.open("https://www.google.com")
                success = True
                launched_methods.append("Default Browser Fallback")

        return {
            "app_key": "chrome",
            "name": name,
            "icon": icon,
            "success": success,
            "launched_methods": launched_methods,
            "web_url": "https://www.google.com",
            "details": "Google Chrome browser opened successfully."
        }

    # 3. Web-only or Protocol-based applications (e.g. YouTube, Gmail, GitHub, Spotify)
    if "web_url" in app_info:
        url = app_info["web_url"]
        try:
            if os.path.exists(chrome_path):
                subprocess.Popen([chrome_path, url])
            else:
                subprocess.Popen(f'start chrome "{url}"', shell=True)
            success = True
            launched_methods.append(f"Opened {url} in Google Chrome")
        except Exception:
            try:
                webbrowser.open(url)
                success = True
                launched_methods.append(f"Opened {url} in default browser")
            except Exception:
                pass

        # Try protocol if present (e.g. Spotify)
        if "protocol" in app_info:
            try:
                os.startfile(app_info["protocol"])
                launched_methods.append(f"Native Protocol ({app_info['protocol']})")
                success = True
            except Exception:
                pass

        return {
            "app_key": app_key,
            "name": name,
            "icon": icon,
            "success": success,
            "launched_methods": launched_methods,
            "web_url": url,
            "details": f"Opened {name} ({url})."
        }

    # 4. Standard Windows Desktop Executables (e.g. calc.exe, notepad.exe, code, explorer.exe)
    if "command" in app_info:
        cmd = app_info["command"]
        try:
            subprocess.Popen(cmd, shell=True)
            success = True
            launched_methods.append(f"Windows Command ({cmd})")
        except Exception as e:
            try:
                os.startfile(cmd)
                success = True
                launched_methods.append(f"os.startfile({cmd})")
            except Exception:
                pass

        return {
            "app_key": app_key,
            "name": name,
            "icon": icon,
            "success": success,
            "launched_methods": launched_methods,
            "details": f"Launched {name} on your Windows machine."
        }

    # 5. Protocol schemes (e.g. ms-settings:, microsoft.windows.camera:)
    if "protocol" in app_info:
        proto = app_info["protocol"]
        try:
            os.startfile(proto)
            success = True
            launched_methods.append(f"Windows URI Protocol ({proto})")
        except Exception:
            try:
                subprocess.Popen(f"start {proto}", shell=True)
                success = True
                launched_methods.append(f"Shell Start ({proto})")
            except Exception:
                pass

        return {
            "app_key": app_key,
            "name": name,
            "icon": icon,
            "success": success,
            "launched_methods": launched_methods,
            "details": f"Opened {name} via Windows protocol {proto}."
        }

    return {
        "app_key": app_key,
        "name": name,
        "icon": icon,
        "success": False,
        "error": "No execution method succeeded."
    }
