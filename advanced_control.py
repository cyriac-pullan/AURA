"""
AURA v2 - Advanced System Control Module
Adds keyboard/mouse emulation, terminal commands, browser automation, and more.
This is the "do anything a human can do" layer.
"""

import subprocess
import os
import time
import logging
from typing import Optional, Dict, Any, List, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARD & MOUSE EMULATION
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    pyautogui.PAUSE = 0.1
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logging.warning("pyautogui not available")

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


def type_text(text: str, interval: float = 0.02) -> bool:
    """Type text using keyboard emulation"""
    if not PYAUTOGUI_AVAILABLE:
        return False
    try:
        # Use clipboard for Unicode support
        if CLIPBOARD_AVAILABLE:
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
        else:
            pyautogui.typewrite(text, interval=interval)
        print(f"Typed: {text[:30]}...")
        return True
    except Exception as e:
        logging.error(f"Type error: {e}")
        return False


def press_key(key: str) -> bool:
    """Press a single key"""
    if not PYAUTOGUI_AVAILABLE:
        return False
    try:
        pyautogui.press(key)
        print(f"Pressed: {key}")
        return True
    except Exception as e:
        logging.error(f"Key press error: {e}")
        return False


def hotkey(*keys) -> bool:
    """Press a key combination (e.g., ctrl+c)"""
    if not PYAUTOGUI_AVAILABLE:
        return False
    try:
        pyautogui.hotkey(*keys)
        print(f"Hotkey: {'+'.join(keys)}")
        return True
    except Exception as e:
        logging.error(f"Hotkey error: {e}")
        return False


def mouse_click(x: int = None, y: int = None, button: str = 'left') -> bool:
    """Click mouse at position (or current position if not specified)"""
    if not PYAUTOGUI_AVAILABLE:
        return False
    try:
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
            print(f"Clicked at ({x}, {y})")
        else:
            pyautogui.click(button=button)
            print("Clicked at current position")
        return True
    except Exception as e:
        logging.error(f"Click error: {e}")
        return False


def mouse_move(x: int, y: int, duration: float = 0.3) -> bool:
    """Move mouse to position"""
    if not PYAUTOGUI_AVAILABLE:
        return False
    try:
        pyautogui.moveTo(x, y, duration=duration)
        print(f"Moved to ({x}, {y})")
        return True
    except Exception as e:
        logging.error(f"Move error: {e}")
        return False


def scroll(clicks: int) -> bool:
    """Scroll up (positive) or down (negative)"""
    if not PYAUTOGUI_AVAILABLE:
        return False
    try:
        pyautogui.scroll(clicks)
        print(f"Scrolled: {clicks}")
        return True
    except Exception as e:
        logging.error(f"Scroll error: {e}")
        return False


def double_click(x: int = None, y: int = None) -> bool:
    """Double click"""
    if not PYAUTOGUI_AVAILABLE:
        return False
    try:
        if x is not None and y is not None:
            pyautogui.doubleClick(x, y)
        else:
            pyautogui.doubleClick()
        print("Double clicked")
        return True
    except Exception as e:
        logging.error(f"Double click error: {e}")
        return False


def right_click(x: int = None, y: int = None) -> bool:
    """Right click"""
    return mouse_click(x, y, button='right')


# ═══════════════════════════════════════════════════════════════════════════════
# TERMINAL & COMMAND EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

def run_terminal_command(command: str, timeout: int = 30) -> Tuple[bool, str]:
    """
    Run a terminal/PowerShell command and return output.
    Returns (success, output)
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.expanduser("~")
        )
        output = result.stdout or result.stderr
        success = result.returncode == 0
        print(f"Command: {command[:50]}... -> {'Success' if success else 'Failed'}")
        return success, output.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def run_powershell(command: str) -> Tuple[bool, str]:
    """Run a PowerShell command"""
    ps_command = f'powershell -Command "{command}"'
    return run_terminal_command(ps_command)


def open_terminal() -> bool:
    """Open Windows Terminal or PowerShell"""
    try:
        subprocess.Popen("wt", shell=True)
        return True
    except:
        try:
            subprocess.Popen("powershell", shell=True)
            return True
        except:
            return False


def run_in_terminal(command: str) -> bool:
    """Open terminal and run a command"""
    try:
        # Open PowerShell with the command
        subprocess.Popen(f'start powershell -NoExit -Command "{command}"', shell=True)
        return True
    except Exception as e:
        logging.error(f"Terminal command error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# GIT OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def git_status(repo_path: str = ".") -> Tuple[bool, str]:
    """Get git status"""
    old_cwd = os.getcwd()
    try:
        os.chdir(repo_path)
        return run_terminal_command("git status")
    finally:
        os.chdir(old_cwd)


def git_pull(repo_path: str = ".") -> Tuple[bool, str]:
    """Pull latest changes"""
    old_cwd = os.getcwd()
    try:
        os.chdir(repo_path)
        return run_terminal_command("git pull")
    finally:
        os.chdir(old_cwd)


def git_commit(message: str, repo_path: str = ".") -> Tuple[bool, str]:
    """Add all and commit"""
    old_cwd = os.getcwd()
    try:
        os.chdir(repo_path)
        run_terminal_command("git add .")
        return run_terminal_command(f'git commit -m "{message}"')
    finally:
        os.chdir(old_cwd)


def git_push(repo_path: str = ".") -> Tuple[bool, str]:
    """Push to remote"""
    old_cwd = os.getcwd()
    try:
        os.chdir(repo_path)
        return run_terminal_command("git push")
    finally:
        os.chdir(old_cwd)


# ═══════════════════════════════════════════════════════════════════════════════
# CLIPBOARD OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard"""
    if CLIPBOARD_AVAILABLE:
        try:
            pyperclip.copy(text)
            print(f"Copied to clipboard: {text[:30]}...")
            return True
        except:
            return False
    return False


def get_clipboard() -> str:
    """Get clipboard content"""
    if CLIPBOARD_AVAILABLE:
        try:
            return pyperclip.paste()
        except:
            return ""
    return ""


def paste_clipboard() -> bool:
    """Paste from clipboard"""
    return hotkey('ctrl', 'v')


# ═══════════════════════════════════════════════════════════════════════════════
# WINDOW MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def minimize_all_windows() -> bool:
    """Minimize all windows (show desktop)"""
    return hotkey('win', 'd')


def switch_window() -> bool:
    """Switch to next window"""
    return hotkey('alt', 'tab')


def close_window() -> bool:
    """Close current window"""
    return hotkey('alt', 'F4')


def maximize_window() -> bool:
    """Maximize current window"""
    return hotkey('win', 'up')


def minimize_window() -> bool:
    """Minimize current window"""
    return hotkey('win', 'down')


def snap_window_left() -> bool:
    """Snap window to left half"""
    return hotkey('win', 'left')


def snap_window_right() -> bool:
    """Snap window to right half"""
    return hotkey('win', 'right')


def open_task_view() -> bool:
    """Open Windows Task View"""
    return hotkey('win', 'tab')


def new_virtual_desktop() -> bool:
    """Create new virtual desktop"""
    return hotkey('win', 'ctrl', 'd')


def close_virtual_desktop() -> bool:
    """Close current virtual desktop"""
    return hotkey('win', 'ctrl', 'F4')


# ═══════════════════════════════════════════════════════════════════════════════
# BROWSER AUTOMATION (Basic - using keyboard/mouse)
# ═══════════════════════════════════════════════════════════════════════════════

def open_browser_url(url: str) -> bool:
    """Open URL in default browser"""
    import webbrowser
    try:
        webbrowser.open(url)
        print(f"Opened: {url}")
        return True
    except:
        return False


def browser_new_tab() -> bool:
    """Open new browser tab"""
    return hotkey('ctrl', 't')


def browser_close_tab() -> bool:
    """Close current browser tab"""
    return hotkey('ctrl', 'w')


def browser_refresh() -> bool:
    """Refresh current page"""
    return hotkey('ctrl', 'r')


def browser_back() -> bool:
    """Go back"""
    return hotkey('alt', 'left')


def browser_forward() -> bool:
    """Go forward"""
    return hotkey('alt', 'right')


def browser_focus_url() -> bool:
    """Focus URL bar"""
    return hotkey('ctrl', 'l')


def browser_go_to(url: str) -> bool:
    """Navigate to URL in current tab"""
    time.sleep(0.2)
    if browser_focus_url():
        time.sleep(0.1)
        if type_text(url):
            time.sleep(0.1)
            return press_key('enter')
    return False


def browser_search(query: str) -> bool:
    """Search in browser"""
    browser_new_tab()
    time.sleep(0.3)
    return browser_go_to(f"https://www.google.com/search?q={query}")


# ═══════════════════════════════════════════════════════════════════════════════
# WHATSAPP WEB AUTOMATION (Basic)
# ═══════════════════════════════════════════════════════════════════════════════

def open_whatsapp() -> bool:
    """Open WhatsApp Web"""
    return open_browser_url("https://web.whatsapp.com")


def whatsapp_send_message(contact: str, message: str) -> bool:
    """
    Send WhatsApp message (requires WhatsApp Web to be logged in)
    Uses URL scheme for direct messaging
    """
    import urllib.parse
    encoded_msg = urllib.parse.quote(message)
    # Use WhatsApp URL scheme
    url = f"https://web.whatsapp.com/send?phone={contact}&text={encoded_msg}"
    open_browser_url(url)
    # Note: User needs to press Enter to send
    print(f"Opened WhatsApp for {contact}. Press Enter to send.")
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL AUTOMATION (Basic)
# ═══════════════════════════════════════════════════════════════════════════════

def compose_email(to: str = "", subject: str = "", body: str = "") -> bool:
    """Open email compose window with pre-filled content"""
    import urllib.parse
    mailto_url = f"mailto:{to}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    return open_browser_url(mailto_url)


def open_gmail_compose() -> bool:
    """Open Gmail compose"""
    return open_browser_url("https://mail.google.com/mail/u/0/#compose")


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN RECORDING
# ═══════════════════════════════════════════════════════════════════════════════

def start_screen_recording() -> bool:
    """Start screen recording using Windows Game Bar"""
    return hotkey('win', 'alt', 'r')


def stop_screen_recording() -> bool:
    """Stop screen recording"""
    return hotkey('win', 'alt', 'r')


def take_screenshot_region() -> bool:
    """Take screenshot of selected region"""
    return hotkey('win', 'shift', 's')


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def select_all() -> bool:
    """Select all"""
    return hotkey('ctrl', 'a')


def copy() -> bool:
    """Copy selection"""
    return hotkey('ctrl', 'c')


def cut() -> bool:
    """Cut selection"""
    return hotkey('ctrl', 'x')


def paste() -> bool:
    """Paste"""
    return hotkey('ctrl', 'v')


def undo() -> bool:
    """Undo"""
    return hotkey('ctrl', 'z')


def redo() -> bool:
    """Redo"""
    return hotkey('ctrl', 'y')


def save() -> bool:
    """Save"""
    return hotkey('ctrl', 's')


def find() -> bool:
    """Find"""
    return hotkey('ctrl', 'f')


def print_document() -> bool:
    """Print"""
    return hotkey('ctrl', 'p')


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT ALL FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Keyboard/Mouse
    "type_text", "press_key", "hotkey", "mouse_click", "mouse_move",
    "scroll", "double_click", "right_click",
    # Terminal
    "run_terminal_command", "run_powershell", "open_terminal", "run_in_terminal",
    # Git
    "git_status", "git_pull", "git_commit", "git_push",
    # Clipboard
    "copy_to_clipboard", "get_clipboard", "paste_clipboard",
    # Window Management
    "minimize_all_windows", "switch_window", "close_window", "maximize_window",
    "minimize_window", "snap_window_left", "snap_window_right",
    "open_task_view", "new_virtual_desktop", "close_virtual_desktop",
    # Browser
    "open_browser_url", "browser_new_tab", "browser_close_tab", "browser_refresh",
    "browser_back", "browser_forward", "browser_focus_url", "browser_go_to",
    "browser_search",
    # WhatsApp
    "open_whatsapp", "whatsapp_send_message",
    # Email
    "compose_email", "open_gmail_compose",
    # Screen
    "start_screen_recording", "stop_screen_recording", "take_screenshot_region",
    # Convenience
    "select_all", "copy", "cut", "paste", "undo", "redo", "save", "find", "print_document",
]


if __name__ == "__main__":
    print("Testing Advanced Control Module...")
    print(f"PyAutoGUI available: {PYAUTOGUI_AVAILABLE}")
    print(f"Clipboard available: {CLIPBOARD_AVAILABLE}")
    
    # Quick test
    print("\nTest: Typing text in 3 seconds...")
    time.sleep(3)
    type_text("Hello from AURA!")
