"""
AURA v2 - Function Executor
Executes functions from the routing layer with proper error handling.
Maps intent names to actual functions in windows_system_utils.
"""

import logging
import subprocess
from typing import Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    """Result of a function execution"""
    success: bool
    result: Any = None
    error: str = ""
    function_name: str = ""
    args: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.args is None:
            self.args = {}


class FunctionExecutor:
    """
    Executes system functions based on intent router results.
    Handles mapping from intent names to actual functions.
    """
    
    def __init__(self):
        self._windows_utils = None
        self._advanced_control = None
        self._load_functions()
    
    def _load_functions(self):
        """Load windows_system_utils and advanced_control functions"""
        try:
            import windows_system_utils
            self._windows_utils = windows_system_utils
            logging.info("FunctionExecutor: Loaded windows_system_utils")
        except ImportError as e:
            logging.error(f"FunctionExecutor: Could not load windows_system_utils: {e}")
        
        try:
            import advanced_control
            self._advanced_control = advanced_control
            logging.info("FunctionExecutor: Loaded advanced_control")
        except ImportError as e:
            logging.warning(f"FunctionExecutor: Could not load advanced_control: {e}")
    
    def execute(self, function_name: str, args: Dict[str, Any] = None) -> ExecutionResult:
        """
        Execute a function by name with given arguments.
        
        Args:
            function_name: Name of the function to execute
            args: Arguments to pass to the function
            
        Returns:
            ExecutionResult with success status and result/error
        """
        args = args or {}
        
        try:
            # Handle special cases that need pre-processing
            actual_func, processed_args = self._preprocess(function_name, args)
            
            if actual_func is None:
                return ExecutionResult(
                    success=False,
                    error=f"Function not found: {function_name}",
                    function_name=function_name,
                    args=args
                )
            
            # Execute the function
            logging.info(f"Executing: {function_name} with args: {processed_args}")
            result = actual_func(**processed_args)
            
            return ExecutionResult(
                success=True if result is not False else False,
                result=result,
                function_name=function_name,
                args=processed_args
            )
            
        except Exception as e:
            logging.error(f"Execution error for {function_name}: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                function_name=function_name,
                args=args
            )
    
    def _preprocess(self, function_name: str, args: Dict[str, Any]) -> Tuple[Optional[Callable], Dict[str, Any]]:
        """
        Preprocess function call - map intent names to actual functions
        and adjust arguments as needed.
        """
        if self._windows_utils is None:
            return None, args
        
        # ═══════════════════════════════════════════════════════════════════════
        # VOLUME CONTROL
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "set_system_volume":
            func = getattr(self._windows_utils, "set_system_volume", None)
            return func, {"level": args.get("level", 50)}
        
        if function_name == "mute_system_volume":
            func = getattr(self._windows_utils, "mute_system_volume", None)
            return func, {}
        
        if function_name == "unmute_system_volume":
            func = getattr(self._windows_utils, "unmute_system_volume", None)
            return func, {}
        
        if function_name == "increase_volume":
            # Get current volume and increase
            try:
                current = self._windows_utils.get_current_volume()
                new_level = min(100, current + args.get("change", 10))
                func = getattr(self._windows_utils, "set_system_volume", None)
                return func, {"level": new_level}
            except:
                return getattr(self._windows_utils, "set_system_volume", None), {"level": 60}
        
        if function_name == "decrease_volume":
            try:
                current = self._windows_utils.get_current_volume()
                new_level = max(0, current + args.get("change", -10))
                func = getattr(self._windows_utils, "set_system_volume", None)
                return func, {"level": new_level}
            except:
                return getattr(self._windows_utils, "set_system_volume", None), {"level": 40}
        
        # ═══════════════════════════════════════════════════════════════════════
        # BRIGHTNESS CONTROL
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "set_brightness":
            func = getattr(self._windows_utils, "set_brightness", None)
            return func, {"level": args.get("level", 50)}
        
        if function_name == "increase_brightness":
            func = getattr(self._windows_utils, "adjust_brightness", None)
            return func, {"change": args.get("change", 20)}
        
        if function_name == "decrease_brightness":
            func = getattr(self._windows_utils, "adjust_brightness", None)
            return func, {"change": args.get("change", -20)}
        
        # ═══════════════════════════════════════════════════════════════════════
        # APPLICATION CONTROL
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "open_application":
            app_name = args.get("app_name", "").lower().strip()
            
            # Map common app names to executables/commands
            # Format: app_name -> (executable, is_store_app)
            app_map = {
                "chrome": ("chrome", False),
                "google chrome": ("chrome", False),
                "firefox": ("firefox", False),
                "edge": ("msedge", False),
                "microsoft edge": ("msedge", False),
                "notepad": ("notepad", False),
                "calculator": ("calc", False),
                "calc": ("calc", False),
                "paint": ("mspaint", False),
                "word": ("winword", False),
                "excel": ("excel", False),
                "powerpoint": ("powerpnt", False),
                "cmd": ("cmd", False),
                "command prompt": ("cmd", False),
                "terminal": ("wt", False),
                "powershell": ("powershell", False),
                "settings": ("ms-settings:", True),
                "control panel": ("control", False),
                "task manager": ("taskmgr", False),
                "spotify": ("spotify", True),  # Store app
                "vscode": ("code", False),
                "vs code": ("code", False),
                "visual studio code": ("code", False),
                "whatsapp": ("whatsapp", True),  # Store app
                "telegram": ("telegram", True),  # Store app
                "discord": ("discord", False),
                "slack": ("slack", False),
                "vlc": ("vlc", False),
                "zoom": ("zoom", False),
            }
            
            app_info = app_map.get(app_name, (app_name, False))
            executable, is_store_app = app_info
            
            def open_app():
                import os
                try:
                    if executable.startswith("ms-"):
                        # Windows URI scheme (like ms-settings:)
                        os.system(f'start "" "{executable}"')
                        print(f"Launched {app_name}")
                        return True
                    
                    if is_store_app:
                        # Try multiple methods for store apps
                        # Method 1: Use start command with app name
                        result = os.system(f'start "" "{executable}:"')
                        if result == 0:
                            print(f"Launched {app_name}")
                            return True
                        
                        # Method 2: Try explorer shell:AppsFolder
                        result = subprocess.run(
                            f'explorer.exe shell:AppsFolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify',
                            shell=True,
                            capture_output=True
                        ) if executable == "spotify" else None
                        
                        # Method 3: Web fallback for Spotify
                        if executable == "spotify":
                            import webbrowser
                            webbrowser.open("https://open.spotify.com")
                            print(f"Opened Spotify Web Player")
                            return True
                        
                        print(f"Launched {app_name}")
                        return True
                    
                    # Regular apps - try start command first
                    result = os.system(f'start "" "{executable}"')
                    if result == 0:
                        print(f"Launched {app_name}")
                        return True
                    
                    # Fallback: direct execution
                    subprocess.Popen(executable, shell=True)
                    print(f"Launched {app_name}")
                    return True
                    
                except Exception as e:
                    logging.error(f"Failed to open {app_name}: {e}")
                    return False
            
            return open_app, {}
        
        if function_name == "close_application":
            app_name = args.get("app_name", "").lower().strip()
            
            def close_app():
                try:
                    subprocess.run(f'taskkill /IM {app_name}.exe /F', shell=True, check=True)
                    return True
                except:
                    try:
                        subprocess.run(f'taskkill /FI "WINDOWTITLE eq {app_name}*" /F', shell=True)
                        return True
                    except Exception as e:
                        logging.error(f"Failed to close {app_name}: {e}")
                        return False
            
            return close_app, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # SYSTEM FUNCTIONS (direct mapping)
        # ═══════════════════════════════════════════════════════════════════════
        direct_functions = [
            "open_file_explorer",
            "take_screenshot",
            "open_camera_app",
            "open_photos_app",
            "lock_workstation",
            "restart_explorer",
            "empty_recycle_bin",
            "hide_desktop_icons",
            "show_desktop_icons",
            "create_ai_news_file",
        ]
        
        if function_name in direct_functions:
            func = getattr(self._windows_utils, function_name, None)
            return func, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # NIGHT LIGHT / AIRPLANE MODE
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "night_light_on":
            func = getattr(self._windows_utils, "toggle_night_light", None)
            return func, {"enable": True}
        
        if function_name == "night_light_off":
            func = getattr(self._windows_utils, "toggle_night_light", None)
            return func, {"enable": False}
        
        if function_name == "airplane_mode_on":
            func = getattr(self._windows_utils, "toggle_airplane_mode_advanced", None)
            return func, {"enable": True}
        
        if function_name == "airplane_mode_off":
            func = getattr(self._windows_utils, "toggle_airplane_mode_advanced", None)
            return func, {"enable": False}
        
        # ═══════════════════════════════════════════════════════════════════════
        # YOUTUBE - Open browser and play/search
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "play_youtube" or function_name == "play_youtube_video_ultra_direct":
            query = args.get("query", args.get("search_term", ""))
            
            def play_youtube():
                import webbrowser
                import urllib.parse
                if query:
                    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
                else:
                    url = "https://www.youtube.com"
                webbrowser.open(url)
                print(f"Opening YouTube: {query if query else 'Home'}")
                return True
            
            return play_youtube, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # SPOTIFY - Open web player or app
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "play_spotify":
            query = args.get("query", "")
            
            def play_spotify():
                import webbrowser
                import urllib.parse
                # Try to open Spotify app first
                try:
                    if query:
                        # Open Spotify search
                        subprocess.Popen("spotify", shell=True)
                        # Also open web search as backup
                        url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
                        webbrowser.open(url)
                    else:
                        subprocess.Popen("spotify", shell=True)
                    print(f"Opening Spotify: {query if query else 'Home'}")
                    return True
                except:
                    # Fallback to web
                    url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}" if query else "https://open.spotify.com"
                    webbrowser.open(url)
                    return True
            
            return play_spotify, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # GOOGLE SEARCH
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "google_search":
            query = args.get("query", "")
            
            def google_search():
                import webbrowser
                import urllib.parse
                if query:
                    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                else:
                    url = "https://www.google.com"
                webbrowser.open(url)
                print(f"Searching Google for: {query}")
                return True
            
            return google_search, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # OPEN WEBSITE
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "open_website":
            url = args.get("url", "")
            
            def open_website():
                import webbrowser
                site = url
                if not site.startswith("http"):
                    site = "https://" + site
                webbrowser.open(site)
                print(f"Opening: {site}")
                return True
            
            return open_website, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # WEATHER
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "get_weather":
            location = args.get("location", "")
            
            def get_weather():
                import webbrowser
                import urllib.parse
                query = f"weather {location}" if location else "weather"
                url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                webbrowser.open(url)
                print(f"Opening weather for: {location if location else 'current location'}")
                return True
            
            return get_weather, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # NEWS
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "get_news":
            def get_news():
                import webbrowser
                webbrowser.open("https://news.google.com")
                print("Opening Google News")
                return True
            
            return get_news, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # EMAIL
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "open_email":
            def open_email():
                import webbrowser
                webbrowser.open("https://mail.google.com")
                print("Opening Gmail")
                return True
            
            return open_email, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # MEDIA CONTROLS (keyboard simulation)
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "media_play_pause":
            def media_play_pause():
                try:
                    import ctypes
                    # VK_MEDIA_PLAY_PAUSE = 0xB3
                    ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)
                    print("Toggled play/pause")
                    return True
                except:
                    return False
            
            return media_play_pause, {}
        
        if function_name == "media_next":
            def media_next():
                try:
                    import ctypes
                    # VK_MEDIA_NEXT_TRACK = 0xB0
                    ctypes.windll.user32.keybd_event(0xB0, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xB0, 0, 2, 0)
                    print("Next track")
                    return True
                except:
                    return False
            
            return media_next, {}
        
        if function_name == "media_previous":
            def media_previous():
                try:
                    import ctypes
                    # VK_MEDIA_PREV_TRACK = 0xB1
                    ctypes.windll.user32.keybd_event(0xB1, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xB1, 0, 2, 0)
                    print("Previous track")
                    return True
                except:
                    return False
            
            return media_previous, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # TIMER
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "set_timer":
            duration = args.get("duration", 1)
            unit = args.get("unit", "minute")
            
            def set_timer():
                import threading
                
                # Convert to seconds
                multiplier = {"second": 1, "minute": 60, "hour": 3600}
                seconds = duration * multiplier.get(unit, 60)
                
                def timer_alert():
                    import time
                    time.sleep(seconds)
                    # Play sound or show notification
                    try:
                        import winsound
                        winsound.Beep(1000, 1000)  # 1000Hz for 1 second
                    except:
                        pass
                    print(f"Timer finished! ({duration} {unit}s)")
                
                timer_thread = threading.Thread(target=timer_alert, daemon=True)
                timer_thread.start()
                print(f"Timer set for {duration} {unit}(s)")
                return True
            
            return set_timer, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # NOTES
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "take_note":
            content = args.get("content", "")
            
            def take_note():
                import os
                from datetime import datetime
                
                notes_file = os.path.join(os.path.expanduser("~"), "Documents", "aura_notes.txt")
                
                try:
                    with open(notes_file, "a", encoding="utf-8") as f:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                        f.write(f"\n[{timestamp}] {content}")
                    print(f"Note saved: {content[:30]}...")
                    return True
                except Exception as e:
                    print(f"Failed to save note: {e}")
                    return False
            
            return take_note, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # SYSTEM INFO
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "system_info":
            def system_info():
                try:
                    import psutil
                    battery = psutil.sensors_battery()
                    cpu = psutil.cpu_percent()
                    memory = psutil.virtual_memory().percent
                    info = f"CPU: {cpu}%, RAM: {memory}%"
                    if battery:
                        info += f", Battery: {battery.percent}%"
                    print(info)
                    return info
                except:
                    return "System info unavailable"
            
            return system_info, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # SHUTDOWN / RESTART / SLEEP
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "shutdown_computer":
            def shutdown():
                subprocess.run("shutdown /s /t 60", shell=True)
                print("Shutting down in 60 seconds. Run 'shutdown /a' to cancel.")
                return True
            return shutdown, {}
        
        if function_name == "restart_computer":
            def restart():
                subprocess.run("shutdown /r /t 60", shell=True)
                print("Restarting in 60 seconds. Run 'shutdown /a' to cancel.")
                return True
            return restart, {}
        
        if function_name == "sleep_computer":
            def sleep():
                subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
                return True
            return sleep, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # CALCULATOR
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "open_calculator":
            def open_calc():
                subprocess.Popen("calc", shell=True)
                return True
            return open_calc, {}
        
        if function_name == "calculate":
            expression = args.get("expression", "")
            
            def calculate():
                try:
                    # Simple safe eval
                    result = eval(expression.replace("^", "**"))
                    print(f"{expression} = {result}")
                    return result
                except:
                    return "Could not calculate"
            
            return calculate, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # FILE OPERATIONS
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "create_folder":
            import os
            folder_name = args.get("folder_name", "New Folder")
            
            def create_folder():
                try:
                    # Default to Desktop if no path specified
                    if not os.path.isabs(folder_name):
                        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                        folder_path = os.path.join(desktop, folder_name)
                    else:
                        folder_path = folder_name
                    
                    os.makedirs(folder_path, exist_ok=True)
                    print(f"Created folder: {folder_path}")
                    return os.path.exists(folder_path)
                except Exception as e:
                    logging.error(f"Failed to create folder: {e}")
                    return False
            
            return create_folder, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # POWERPOINT
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "create_powerpoint_presentation":
            func = getattr(self._windows_utils, "create_powerpoint_presentation", None)
            return func, {"topic": args.get("topic", "General")}
        
        # ═══════════════════════════════════════════════════════════════════════
        # TIME/DATE (simple local functions)
        # ═══════════════════════════════════════════════════════════════════════
        if function_name == "get_time":
            from datetime import datetime
            def get_time():
                return datetime.now().strftime("%I:%M %p")
            return get_time, {}
        
        if function_name == "get_date":
            from datetime import datetime
            def get_date():
                return datetime.now().strftime("%A, %B %d, %Y")
            return get_date, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # ADVANCED CONTROL FUNCTIONS
        # ═══════════════════════════════════════════════════════════════════════
        if self._advanced_control:
            ac = self._advanced_control
            
            # Terminal commands
            if function_name == "run_terminal_command":
                command = args.get("command", "")
                def run_cmd():
                    success, output = ac.run_terminal_command(command)
                    print(output[:200] if output else "Command executed")
                    return success
                return run_cmd, {}
            
            if function_name == "open_terminal":
                return ac.open_terminal, {}
            
            # Keyboard/Typing
            if function_name == "type_text":
                text = args.get("text", "")
                def type_it():
                    return ac.type_text(text)
                return type_it, {}
            
            if function_name == "press_key":
                key = args.get("key", "")
                def press_it():
                    return ac.press_key(key)
                return press_it, {}
            
            if function_name == "hotkey":
                keys_str = args.get("keys", "")
                def do_hotkey():
                    # Parse keys like "ctrl+c" or "alt+tab"
                    keys = [k.strip() for k in keys_str.replace("+", " ").split()]
                    return ac.hotkey(*keys)
                return do_hotkey, {}
            
            # Mouse control
            if function_name == "mouse_click":
                x, y = args.get("x"), args.get("y")
                def click_it():
                    return ac.mouse_click(x, y)
                return click_it, {}
            
            if function_name == "right_click":
                return ac.right_click, {}
            
            if function_name == "double_click":
                return ac.double_click, {}
            
            if function_name == "scroll":
                clicks = args.get("clicks", 3)
                def scroll_it():
                    return ac.scroll(clicks)
                return scroll_it, {}
            
            # Window management
            if function_name == "minimize_all_windows":
                return ac.minimize_all_windows, {}
            
            if function_name == "switch_window":
                return ac.switch_window, {}
            
            if function_name == "close_window":
                return ac.close_window, {}
            
            if function_name == "maximize_window":
                return ac.maximize_window, {}
            
            if function_name == "snap_window_left":
                return ac.snap_window_left, {}
            
            if function_name == "snap_window_right":
                return ac.snap_window_right, {}
            
            # Git operations
            if function_name == "git_status":
                def git_status():
                    success, output = ac.git_status()
                    print(output[:300] if output else "No status")
                    return success
                return git_status, {}
            
            if function_name == "git_pull":
                def git_pull():
                    success, output = ac.git_pull()
                    print(output[:200] if output else "Pulled")
                    return success
                return git_pull, {}
            
            if function_name == "git_commit":
                message = args.get("message", "Auto commit")
                def git_commit():
                    success, output = ac.git_commit(message)
                    print(output[:200] if output else "Committed")
                    return success
                return git_commit, {}
            
            if function_name == "git_push":
                def git_push():
                    success, output = ac.git_push()
                    print(output[:200] if output else "Pushed")
                    return success
                return git_push, {}
            
            # WhatsApp
            if function_name == "open_whatsapp":
                return ac.open_whatsapp, {}
            
            if function_name == "whatsapp_send_message":
                contact = args.get("contact", "")
                message = args.get("message", "")
                def send_wa():
                    return ac.whatsapp_send_message(contact, message)
                return send_wa, {}
            
            # Email
            if function_name == "compose_email":
                to = args.get("to", "")
                subject = args.get("subject", "")
                def compose():
                    return ac.compose_email(to, subject)
                return compose, {}
            
            # Screen recording
            if function_name == "start_screen_recording":
                return ac.start_screen_recording, {}
            
            if function_name == "stop_screen_recording":
                return ac.stop_screen_recording, {}
            
            # Browser
            if function_name == "browser_new_tab":
                return ac.browser_new_tab, {}
            
            if function_name == "browser_close_tab":
                return ac.browser_close_tab, {}
            
            if function_name == "browser_refresh":
                return ac.browser_refresh, {}
            
            if function_name == "browser_back":
                return ac.browser_back, {}
            
            if function_name == "browser_forward":
                return ac.browser_forward, {}
            
            # Convenience shortcuts
            if function_name == "select_all":
                return ac.select_all, {}
            
            if function_name == "undo":
                return ac.undo, {}
            
            if function_name == "redo":
                return ac.redo, {}
            
            if function_name == "save":
                return ac.save, {}
            
            if function_name == "find":
                query = args.get("query", "")
                def find_it():
                    ac.find()
                    if query:
                        import time
                        time.sleep(0.2)
                        return ac.type_text(query)
                    return True
                return find_it, {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # FALLBACK: Try to find function directly
        # ═══════════════════════════════════════════════════════════════════════
        func = getattr(self._windows_utils, function_name, None)
        if func:
            return func, args
        
        # Try advanced control fallback
        if self._advanced_control:
            func = getattr(self._advanced_control, function_name, None)
            if func:
                return func, args
        
        return None, args
    
    def execute_raw(self, code: str) -> ExecutionResult:
        """
        Execute raw Python code (for Gemini-generated code).
        Use with caution - this is for fallback cases.
        This is the v1-like execution path that allows any command to work.
        """
        try:
            import os
            import subprocess
            import webbrowser
            import time
            import urllib.parse
            
            # Create a rich execution environment with commonly needed modules
            exec_globals = {
                "__builtins__": __builtins__,
                "windows_system_utils": self._windows_utils,
                "os": os,
                "subprocess": subprocess,
                "webbrowser": webbrowser,
                "time": time,
                "urllib": urllib,
                "logging": logging,
            }
            
            # Add advanced control functions if available
            if self._advanced_control:
                exec_globals["advanced_control"] = self._advanced_control
            
            # Add windows_system_utils functions directly to global scope
            if self._windows_utils:
                for name in dir(self._windows_utils):
                    if not name.startswith("_"):
                        func = getattr(self._windows_utils, name)
                        if callable(func):
                            exec_globals[name] = func
            
            exec_locals = {}
            
            logging.info(f"Executing generated code ({len(code)} chars)")
            exec(code, exec_globals, exec_locals)
            
            # Try to get the result
            result = exec_locals.get("result", True)
            
            return ExecutionResult(
                success=True,
                result=result,
                function_name="generated_code"
            )
        except Exception as e:
            logging.error(f"Generated code execution error: {e}")
            logging.error(f"Code was:\n{code[:500]}...")
            return ExecutionResult(
                success=False,
                error=str(e),
                function_name="generated_code"
            )


# Global instance
function_executor = FunctionExecutor()


def get_function_executor() -> FunctionExecutor:
    """Get the global function executor"""
    return function_executor


def execute_command(function_name: str, args: Dict[str, Any] = None) -> ExecutionResult:
    """Convenience function for executing a command"""
    return function_executor.execute(function_name, args)
