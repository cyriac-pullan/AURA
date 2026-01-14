"""
AURA v2 - Local Intent Router
Fast, local intent classification WITHOUT calling LLM.
This is the critical cost-saving layer that routes commands locally when possible.

Routing Logic:
- confidence >= 0.85 → LOCAL execution (0 tokens)
- confidence 0.50-0.85 → Gemini intent-only mode (~100 tokens)
- confidence < 0.50 → Gemini full reasoning (~500 tokens)
- conversation trigger → Gemini chat mode (~300 tokens)
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Tuple

# Try to import fuzzy matching
try:
    from rapidfuzz import fuzz, process
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    logging.warning("rapidfuzz not installed. Fuzzy matching disabled. Install with: pip install rapidfuzz")


@dataclass
class RouteResult:
    """Result of intent classification"""
    confidence: float                    # 0.0 - 1.0
    function: Optional[str] = None       # Function name to call
    args: Dict[str, Any] = field(default_factory=dict)  # Extracted arguments
    is_conversation: bool = False        # Should trigger chat mode
    match_type: str = "none"             # keyword/pattern/fuzzy/none
    raw_command: str = ""                # Original command


class IntentRouter:
    """
    Fast, local intent classification - NO LLM CALLS.
    This dramatically reduces API costs by handling routine commands locally.
    """
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONVERSATION TRIGGERS - Commands that should go to Gemini chat mode
    # ═══════════════════════════════════════════════════════════════════════════
    CONVERSATION_TRIGGERS = [
        "what is", "what's", "who is", "who's", "why", "how does", "how do",
        "explain", "tell me about", "can you", "could you", "would you",
        "what do you think", "your opinion", "help me understand",
        "what are", "when did", "when was", "where is", "where are",
        "describe", "definition of", "meaning of", "how to",
        "do you know", "have you heard", "teach me"
    ]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FUNCTION REGISTRY - Maps intents to functions with triggers and patterns
    # ═══════════════════════════════════════════════════════════════════════════
    FUNCTION_REGISTRY = {
        # ───────────────────────────────────────────────────────────────────────
        # AUDIO / VOLUME CONTROL
        # ───────────────────────────────────────────────────────────────────────
        "set_system_volume": {
            "keywords": ["volume", "sound level", "audio level"],
            "patterns": [
                r"(?:set|change|adjust)\s+(?:the\s+)?volume\s+(?:to\s+)?(\d+)",
                r"volume\s+(?:to\s+)?(\d+)",
                r"(\d+)\s*%?\s*volume",
                r"turn\s+(?:the\s+)?volume\s+(?:to\s+)?(\d+)",
            ],
            "extractor": lambda m: {"level": int(m.group(1))}
        },
        "mute_system_volume": {
            "keywords": ["mute", "silence the audio", "silence sound", "quiet"],
            "patterns": [
                r"\bmute\b",
                r"mute\s+(?:the\s+)?(?:volume|sound|audio)",
                r"silence\s+(?:the\s+)?(?:volume|sound|audio)",
            ],
            "extractor": lambda m: {}
        },
        "unmute_system_volume": {
            "keywords": ["unmute"],
            "patterns": [
                r"\bunmute\b",
                r"unmute\s+(?:the\s+)?(?:volume|sound|audio)",
                r"sound\s+on",
                r"audio\s+on",
            ],
            "extractor": lambda m: {}
        },
        "increase_volume": {
            "keywords": ["volume up", "louder", "increase volume", "turn up"],
            "patterns": [
                r"(?:turn|volume)\s+up",
                r"increase\s+(?:the\s+)?volume",
                r"louder",
                r"raise\s+(?:the\s+)?volume",
            ],
            "extractor": lambda m: {"change": 10}
        },
        "decrease_volume": {
            "keywords": ["volume down", "quieter", "decrease volume", "turn down"],
            "patterns": [
                r"(?:turn|volume)\s+down",
                r"decrease\s+(?:the\s+)?volume",
                r"quieter",
                r"lower\s+(?:the\s+)?volume",
            ],
            "extractor": lambda m: {"change": -10}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # BRIGHTNESS CONTROL
        # ───────────────────────────────────────────────────────────────────────
        "set_brightness": {
            "keywords": ["brightness", "screen brightness", "display brightness"],
            "patterns": [
                r"(?:set|change|adjust)\s+(?:the\s+)?brightness\s+(?:to\s+)?(\d+)",
                r"brightness\s+(?:to\s+)?(\d+)",
                r"(\d+)\s*%?\s*brightness",
            ],
            "extractor": lambda m: {"level": int(m.group(1))}
        },
        "increase_brightness": {
            "keywords": ["brightness up", "brighter", "increase brightness"],
            "patterns": [
                r"(?:brightness|screen)\s+up",
                r"increase\s+(?:the\s+)?brightness",
                r"brighter",
                r"make\s+(?:it\s+)?brighter",
            ],
            "extractor": lambda m: {"change": 20}
        },
        "decrease_brightness": {
            "keywords": ["brightness down", "dimmer", "decrease brightness", "darker"],
            "patterns": [
                r"(?:brightness|screen)\s+down",
                r"decrease\s+(?:the\s+)?brightness",
                r"dimmer",
                r"darker",
                r"make\s+(?:it\s+)?(?:dimmer|darker)",
            ],
            "extractor": lambda m: {"change": -20}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # APPLICATION CONTROL
        # ───────────────────────────────────────────────────────────────────────
        "open_application": {
            "keywords": ["open", "launch", "start", "run"],
            "patterns": [
                r"(?:open|launch|start|run)\s+(.+?)(?:\s+app(?:lication)?)?$",
            ],
            "extractor": lambda m: {"app_name": m.group(1).strip()}
        },
        "close_application": {
            "keywords": ["close", "exit", "quit", "kill", "terminate"],
            "patterns": [
                r"(?:close|exit|quit|kill|terminate)\s+(.+?)(?:\s+app(?:lication)?)?$",
            ],
            "extractor": lambda m: {"app_name": m.group(1).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # FILE EXPLORER
        # ───────────────────────────────────────────────────────────────────────
        "open_file_explorer": {
            "keywords": ["file explorer", "files", "explorer", "my computer", "this pc"],
            "patterns": [
                r"open\s+(?:file\s+)?explorer",
                r"open\s+files",
                r"open\s+my\s+computer",
                r"open\s+this\s+pc",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # SCREENSHOT
        # ───────────────────────────────────────────────────────────────────────
        "take_screenshot": {
            "keywords": ["screenshot", "screen capture", "capture screen", "print screen"],
            "patterns": [
                r"(?:take|capture)\s+(?:a\s+)?screenshot",
                r"screenshot",
                r"capture\s+(?:the\s+)?screen",
                r"print\s+screen",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # CAMERA
        # ───────────────────────────────────────────────────────────────────────
        "open_camera_app": {
            "keywords": ["camera", "webcam"],
            "patterns": [
                r"open\s+(?:the\s+)?camera",
                r"camera",
                r"webcam",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # SYSTEM CONTROL
        # ───────────────────────────────────────────────────────────────────────
        "lock_workstation": {
            "keywords": ["lock", "lock computer", "lock pc", "lock screen"],
            "patterns": [
                r"lock\s+(?:the\s+)?(?:computer|pc|screen|workstation)",
                r"lock\s+it",
            ],
            "extractor": lambda m: {}
        },
        "restart_explorer": {
            "keywords": ["restart explorer", "refresh explorer"],
            "patterns": [
                r"restart\s+(?:windows\s+)?explorer",
                r"refresh\s+explorer",
            ],
            "extractor": lambda m: {}
        },
        "empty_recycle_bin": {
            "keywords": ["empty recycle bin", "clear recycle bin", "empty trash"],
            "patterns": [
                r"(?:empty|clear)\s+(?:the\s+)?recycle\s+bin",
                r"(?:empty|clear)\s+(?:the\s+)?trash",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # NIGHT LIGHT / AIRPLANE MODE
        # ───────────────────────────────────────────────────────────────────────
        "night_light_on": {
            "keywords": ["night light on", "enable night light", "turn on night light"],
            "patterns": [
                r"(?:turn\s+on|enable)\s+night\s+light",
                r"night\s+light\s+on",
            ],
            "extractor": lambda m: {"enable": True}
        },
        "night_light_off": {
            "keywords": ["night light off", "disable night light", "turn off night light"],
            "patterns": [
                r"(?:turn\s+off|disable)\s+night\s+light",
                r"night\s+light\s+off",
            ],
            "extractor": lambda m: {"enable": False}
        },
        "airplane_mode_on": {
            "keywords": ["airplane mode on", "enable airplane mode", "flight mode on"],
            "patterns": [
                r"(?:turn\s+on|enable)\s+(?:airplane|flight)\s+mode",
                r"(?:airplane|flight)\s+mode\s+on",
            ],
            "extractor": lambda m: {"enable": True}
        },
        "airplane_mode_off": {
            "keywords": ["airplane mode off", "disable airplane mode", "flight mode off"],
            "patterns": [
                r"(?:turn\s+off|disable)\s+(?:airplane|flight)\s+mode",
                r"(?:airplane|flight)\s+mode\s+off",
            ],
            "extractor": lambda m: {"enable": False}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # DESKTOP ICONS
        # ───────────────────────────────────────────────────────────────────────
        "hide_desktop_icons": {
            "keywords": ["hide desktop icons", "hide icons"],
            "patterns": [
                r"hide\s+(?:the\s+)?(?:desktop\s+)?icons",
            ],
            "extractor": lambda m: {}
        },
        "show_desktop_icons": {
            "keywords": ["show desktop icons", "show icons"],
            "patterns": [
                r"show\s+(?:the\s+)?(?:desktop\s+)?icons",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # YOUTUBE - Play videos, search
        # ───────────────────────────────────────────────────────────────────────
        "play_youtube": {
            "keywords": ["youtube", "play on youtube", "yt"],
            "patterns": [
                r"(?:play|search|find)\s+(.+?)\s+on\s+youtube",
                r"(?:play|search|find)\s+(.+?)\s+on\s+yt",
                r"youtube\s+(?:play\s+)?(.+)",
                r"open\s+youtube\s+and\s+(?:play|search)\s+(.+)",
                r"play\s+(.+?)\s+(?:on\s+)?(?:youtube|yt)",
                r"yt\s+(.+)",
            ],
            "extractor": lambda m: {"query": m.group(1).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # SPOTIFY - Play music
        # ───────────────────────────────────────────────────────────────────────
        "play_spotify": {
            "keywords": ["spotify", "play on spotify", "play music"],
            "patterns": [
                r"(?:play|search)\s+(.+?)\s+on\s+spotify",
                r"spotify\s+(?:play\s+)?(.+)",
                r"play\s+(.+?)\s+(?:on\s+)?spotify",
                r"play\s+music\s+(.+)",
            ],
            "extractor": lambda m: {"query": m.group(1).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # GOOGLE SEARCH
        # ───────────────────────────────────────────────────────────────────────
        "google_search": {
            "keywords": ["google", "search for", "search google", "look up"],
            "patterns": [
                r"(?:google|search|search for|look up)\s+(.+)",
                r"search\s+google\s+for\s+(.+)",
                r"find\s+information\s+(?:about|on)\s+(.+)",
            ],
            "extractor": lambda m: {"query": m.group(1).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # OPEN WEBSITE
        # ───────────────────────────────────────────────────────────────────────
        "open_website": {
            "keywords": ["go to", "visit", "navigate to"],
            "patterns": [
                r"(?:go to|open|visit|navigate to)\s+(.+\.(?:com|org|net|io|edu|gov|co|in).*)",
                r"open\s+(?:the\s+)?website\s+(.+)",
                r"browse\s+(?:to\s+)?(.+\.(?:com|org|net|io|edu|gov|co|in).*)",
            ],
            "extractor": lambda m: {"url": m.group(1).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # WEATHER
        # ───────────────────────────────────────────────────────────────────────
        "get_weather": {
            "keywords": ["weather", "temperature", "forecast"],
            "patterns": [
                r"(?:what's|whats|what is)\s+the\s+weather",
                r"weather\s+(?:in\s+)?(.+)?",
                r"(?:how's|hows|how is)\s+the\s+weather",
                r"temperature\s+(?:in\s+)?(.+)?",
            ],
            "extractor": lambda m: {"location": m.group(1).strip() if m.lastindex and m.group(1) else "current location"}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # TIME AND DATE
        # ───────────────────────────────────────────────────────────────────────
        "get_time": {
            "keywords": ["time", "what time"],
            "patterns": [
                r"(?:what's|whats|what is)\s+the\s+time",
                r"current\s+time",
                r"tell\s+(?:me\s+)?the\s+time",
            ],
            "extractor": lambda m: {}
        },
        "get_date": {
            "keywords": ["date", "today's date", "today"],
            "patterns": [
                r"(?:what's|whats|what is)\s+(?:the\s+)?date",
                r"(?:what's|whats|what is)\s+today",
                r"today'?s?\s+date",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # TIMER AND ALARM
        # ───────────────────────────────────────────────────────────────────────
        "set_timer": {
            "keywords": ["timer", "countdown"],
            "patterns": [
                r"(?:set|start)\s+(?:a\s+)?timer\s+(?:for\s+)?(\d+)\s*(second|minute|hour)s?",
                r"timer\s+(\d+)\s*(second|minute|hour)s?",
                r"countdown\s+(\d+)\s*(second|minute|hour)s?",
            ],
            "extractor": lambda m: {"duration": int(m.group(1)), "unit": m.group(2)}
        },
        "set_reminder": {
            "keywords": ["remind", "reminder"],
            "patterns": [
                r"remind\s+me\s+(?:to\s+)?(.+)\s+in\s+(\d+)\s*(minute|hour)s?",
                r"set\s+(?:a\s+)?reminder\s+(?:to\s+)?(.+)",
            ],
            "extractor": lambda m: {"message": m.group(1).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # MEDIA CONTROLS (Global)
        # ───────────────────────────────────────────────────────────────────────
        "media_play_pause": {
            "keywords": ["pause", "resume", "play pause"],
            "patterns": [
                r"\bpause\b",
                r"\bresume\b",
                r"play\s*pause",
            ],
            "extractor": lambda m: {}
        },
        "media_next": {
            "keywords": ["next track", "skip", "next song"],
            "patterns": [
                r"(?:next|skip)\s+(?:track|song)?",
                r"skip\s+this",
            ],
            "extractor": lambda m: {}
        },
        "media_previous": {
            "keywords": ["previous track", "previous song", "go back"],
            "patterns": [
                r"(?:previous|last)\s+(?:track|song)?",
                r"go\s+back",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # FILE / FOLDER OPERATIONS
        # ───────────────────────────────────────────────────────────────────────
        "create_folder": {
            "keywords": ["create folder", "make folder", "new folder", "create directory"],
            "patterns": [
                r"(?:create|make|new)\s+(?:a\s+)?folder\s+(?:named|called)?\s*(.+)",
                r"(?:create|make|new)\s+(?:a\s+)?directory\s+(?:named|called)?\s*(.+)",
            ],
            "extractor": lambda m: {"folder_name": m.group(1).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # NOTES
        # ───────────────────────────────────────────────────────────────────────
        "take_note": {
            "keywords": ["note", "write down", "remember this"],
            "patterns": [
                r"(?:take|make|create)\s+(?:a\s+)?note\s*(?::|that)?\s*(.+)",
                r"(?:write|jot)\s+down\s+(.+)",
                r"remember\s+(?:this\s*:|that\s*)?\s*(.+)",
            ],
            "extractor": lambda m: {"content": m.group(1).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # SYSTEM INFO
        # ───────────────────────────────────────────────────────────────────────
        "system_info": {
            "keywords": ["system info", "battery", "cpu", "memory", "ram"],
            "patterns": [
                r"(?:show|get|display)\s+system\s+info",
                r"battery\s+(?:level|status|percentage)",
                r"(?:how much|what's the)\s+(?:battery|ram|cpu)",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # SHUTDOWN / RESTART / SLEEP
        # ───────────────────────────────────────────────────────────────────────
        "shutdown_computer": {
            "keywords": ["shutdown", "shut down", "power off"],
            "patterns": [
                r"(?:shut\s*down|power\s+off)\s+(?:the\s+)?(?:computer|pc|system)",
                r"shutdown",
            ],
            "extractor": lambda m: {}
        },
        "restart_computer": {
            "keywords": ["restart", "reboot"],
            "patterns": [
                r"(?:restart|reboot)\s+(?:the\s+)?(?:computer|pc|system)",
                r"restart",
            ],
            "extractor": lambda m: {}
        },
        "sleep_computer": {
            "keywords": ["sleep", "standby"],
            "patterns": [
                r"(?:put|go)\s+(?:the\s+)?(?:computer|pc)\s+to\s+sleep",
                r"sleep\s+(?:mode)?",
                r"standby",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # EMAIL
        # ───────────────────────────────────────────────────────────────────────
        "open_email": {
            "keywords": ["email", "gmail", "mail", "inbox"],
            "patterns": [
                r"open\s+(?:my\s+)?(?:email|gmail|mail|inbox)",
                r"check\s+(?:my\s+)?(?:email|mail|inbox)",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # CALCULATOR / MATH
        # ───────────────────────────────────────────────────────────────────────
        "calculate": {
            "keywords": ["calculate", "calculator", "math"],
            "patterns": [
                r"(?:calculate|compute|what is)\s+(\d+[\+\-\*\/\^]\d+.*)",
                r"(\d+)\s*(?:plus|minus|times|divided by)\s*(\d+)",
            ],
            "extractor": lambda m: {"expression": m.group(0)}
        },
        "open_calculator": {
            "keywords": ["open calculator"],
            "patterns": [
                r"open\s+(?:the\s+)?calculator",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # CLIPBOARD
        # ───────────────────────────────────────────────────────────────────────
        "copy_text": {
            "keywords": ["copy this", "copy that"],
            "patterns": [
                r"copy\s+(?:this|that|it)",
            ],
            "extractor": lambda m: {}
        },
        "paste_text": {
            "keywords": ["paste"],
            "patterns": [
                r"paste\s*(?:it)?",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # POWERPOINT
        # ───────────────────────────────────────────────────────────────────────
        "create_powerpoint_presentation": {
            "keywords": ["create ppt", "make ppt", "powerpoint", "presentation"],
            "patterns": [
                r"(?:create|make|generate)\s+(?:a\s+)?(?:ppt|powerpoint|presentation)\s+(?:about|on|based on)\s+(.+)",
            ],
            "extractor": lambda m: {"topic": m.group(1).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # NEWS
        # ───────────────────────────────────────────────────────────────────────
        "get_news": {
            "keywords": ["news", "headlines"],
            "patterns": [
                r"(?:get|show|read|tell me)\s+(?:the\s+)?(?:latest\s+)?news",
                r"(?:what's|whats|what are)\s+(?:the\s+)?(?:latest\s+)?(?:news|headlines)",
            ],
            "extractor": lambda m: {}
        },
        "create_ai_news_file": {
            "keywords": ["ai news", "artificial intelligence news"],
            "patterns": [
                r"(?:create|get|show|fetch)\s+(?:the\s+)?(?:latest\s+)?ai\s+news",
                r"ai\s+news",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # TERMINAL / COMMAND LINE
        # ───────────────────────────────────────────────────────────────────────
        "run_terminal_command": {
            "keywords": ["run command", "execute", "terminal", "cmd"],
            "patterns": [
                r"(?:run|execute)\s+(?:the\s+)?(?:command|cmd)\s+(.+)",
                r"in\s+terminal\s+(?:run|execute)\s+(.+)",
                r"terminal\s+(.+)",
            ],
            "extractor": lambda m: {"command": m.group(1).strip()}
        },
        "open_terminal": {
            "keywords": ["open terminal", "open powershell", "open cmd"],
            "patterns": [
                r"open\s+(?:the\s+)?(?:terminal|powershell|cmd|command\s+prompt)",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # KEYBOARD / TYPING
        # ───────────────────────────────────────────────────────────────────────
        "type_text": {
            "keywords": ["type", "write"],
            "patterns": [
                r"type\s+(.+)",
                r"write\s+(?:out\s+)?(.+)",
            ],
            "extractor": lambda m: {"text": m.group(1).strip()}
        },
        "press_key": {
            "keywords": ["press", "hit key"],
            "patterns": [
                r"press\s+(?:the\s+)?(?:key\s+)?(.+)",
                r"hit\s+(?:the\s+)?(?:key\s+)?(.+)",
            ],
            "extractor": lambda m: {"key": m.group(1).strip().lower()}
        },
        "hotkey": {
            "keywords": ["shortcut", "hotkey", "key combination"],
            "patterns": [
                r"(?:press|use)\s+(?:the\s+)?(?:shortcut|hotkey)\s+(.+)",
                r"ctrl\s*\+\s*(.+)",
                r"alt\s*\+\s*(.+)",
            ],
            "extractor": lambda m: {"keys": m.group(0).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # MOUSE CONTROL
        # ───────────────────────────────────────────────────────────────────────
        "mouse_click": {
            "keywords": ["click", "left click"],
            "patterns": [
                r"click\s+(?:at\s+)?(?:(\d+)\s*,?\s*(\d+))?",
                r"left\s+click",
            ],
            "extractor": lambda m: {"x": int(m.group(1)) if m.lastindex >= 1 and m.group(1) else None, 
                                     "y": int(m.group(2)) if m.lastindex >= 2 and m.group(2) else None}
        },
        "right_click": {
            "keywords": ["right click"],
            "patterns": [
                r"right\s+click",
            ],
            "extractor": lambda m: {}
        },
        "double_click": {
            "keywords": ["double click"],
            "patterns": [
                r"double\s+click",
            ],
            "extractor": lambda m: {}
        },
        "scroll": {
            "keywords": ["scroll up", "scroll down"],
            "patterns": [
                r"scroll\s+(up|down)(?:\s+(\d+))?",
            ],
            "extractor": lambda m: {"clicks": int(m.group(2) or 3) * (1 if m.group(1) == "up" else -1)}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # WINDOW MANAGEMENT
        # ───────────────────────────────────────────────────────────────────────
        "minimize_all_windows": {
            "keywords": ["show desktop", "minimize all"],
            "patterns": [
                r"(?:show|go to)\s+(?:the\s+)?desktop",
                r"minimize\s+all\s+(?:windows)?",
            ],
            "extractor": lambda m: {}
        },
        "switch_window": {
            "keywords": ["switch window", "next window", "alt tab"],
            "patterns": [
                r"switch\s+(?:to\s+next\s+)?window",
                r"alt\s+tab",
                r"next\s+window",
            ],
            "extractor": lambda m: {}
        },
        "close_window": {
            "keywords": ["close window", "close this"],
            "patterns": [
                r"close\s+(?:this\s+)?window",
                r"alt\s+f4",
            ],
            "extractor": lambda m: {}
        },
        "maximize_window": {
            "keywords": ["maximize window", "full screen"],
            "patterns": [
                r"maximize\s+(?:the\s+)?window",
                r"(?:go\s+)?full\s+screen",
            ],
            "extractor": lambda m: {}
        },
        "snap_window_left": {
            "keywords": ["snap left", "window left"],
            "patterns": [
                r"snap\s+(?:window\s+)?(?:to\s+)?left",
                r"move\s+window\s+(?:to\s+)?left",
            ],
            "extractor": lambda m: {}
        },
        "snap_window_right": {
            "keywords": ["snap right", "window right"],
            "patterns": [
                r"snap\s+(?:window\s+)?(?:to\s+)?right",
                r"move\s+window\s+(?:to\s+)?right",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # GIT OPERATIONS
        # ───────────────────────────────────────────────────────────────────────
        "git_status": {
            "keywords": ["git status"],
            "patterns": [
                r"git\s+status",
                r"(?:show|check)\s+git\s+status",
            ],
            "extractor": lambda m: {}
        },
        "git_pull": {
            "keywords": ["git pull"],
            "patterns": [
                r"git\s+pull",
                r"pull\s+(?:the\s+)?(?:latest\s+)?(?:changes|code)",
            ],
            "extractor": lambda m: {}
        },
        "git_commit": {
            "keywords": ["git commit"],
            "patterns": [
                r"git\s+commit\s+(?:with\s+message\s+)?(.+)?",
                r"commit\s+(?:with\s+message\s+)?(.+)?",
            ],
            "extractor": lambda m: {"message": m.group(1).strip() if m.lastindex >= 1 and m.group(1) else "Auto commit"}
        },
        "git_push": {
            "keywords": ["git push"],
            "patterns": [
                r"git\s+push",
                r"push\s+(?:the\s+)?(?:code|changes)",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # WHATSAPP
        # ───────────────────────────────────────────────────────────────────────
        "open_whatsapp": {
            "keywords": ["whatsapp", "open whatsapp"],
            "patterns": [
                r"open\s+whatsapp",
            ],
            "extractor": lambda m: {}
        },
        "whatsapp_send_message": {
            "keywords": ["whatsapp message", "send whatsapp"],
            "patterns": [
                r"(?:send|message)\s+(?:on\s+)?whatsapp\s+(?:to\s+)?(.+?)\s+(?:saying|message|that)\s+(.+)",
                r"whatsapp\s+(.+?)\s+(?:saying|message)\s+(.+)",
            ],
            "extractor": lambda m: {"contact": m.group(1).strip(), "message": m.group(2).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # EMAIL COMPOSE
        # ───────────────────────────────────────────────────────────────────────
        "compose_email": {
            "keywords": ["compose email", "write email", "send email"],
            "patterns": [
                r"(?:compose|write|draft|send)\s+(?:an?\s+)?email\s+to\s+(.+?)\s+(?:about|subject|regarding)\s+(.+)",
                r"email\s+(.+?)\s+about\s+(.+)",
            ],
            "extractor": lambda m: {"to": m.group(1).strip(), "subject": m.group(2).strip()}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # SCREEN RECORDING
        # ───────────────────────────────────────────────────────────────────────
        "start_screen_recording": {
            "keywords": ["record screen", "start recording"],
            "patterns": [
                r"(?:start|begin)\s+(?:screen\s+)?recording",
                r"record\s+(?:the\s+)?screen",
            ],
            "extractor": lambda m: {}
        },
        "stop_screen_recording": {
            "keywords": ["stop recording"],
            "patterns": [
                r"stop\s+(?:screen\s+)?recording",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # BROWSER CONTROL
        # ───────────────────────────────────────────────────────────────────────
        "browser_new_tab": {
            "keywords": ["new tab"],
            "patterns": [
                r"(?:open\s+)?(?:a\s+)?new\s+tab",
            ],
            "extractor": lambda m: {}
        },
        "browser_close_tab": {
            "keywords": ["close tab"],
            "patterns": [
                r"close\s+(?:this\s+)?tab",
            ],
            "extractor": lambda m: {}
        },
        "browser_refresh": {
            "keywords": ["refresh", "reload"],
            "patterns": [
                r"refresh\s+(?:the\s+)?(?:page)?",
                r"reload\s+(?:the\s+)?(?:page)?",
            ],
            "extractor": lambda m: {}
        },
        "browser_back": {
            "keywords": ["go back"],
            "patterns": [
                r"go\s+back",
                r"previous\s+page",
            ],
            "extractor": lambda m: {}
        },
        "browser_forward": {
            "keywords": ["go forward"],
            "patterns": [
                r"go\s+forward",
                r"next\s+page",
            ],
            "extractor": lambda m: {}
        },
        
        # ───────────────────────────────────────────────────────────────────────
        # CONVENIENCE SHORTCUTS
        # ───────────────────────────────────────────────────────────────────────
        "select_all": {
            "keywords": ["select all"],
            "patterns": [
                r"select\s+all",
            ],
            "extractor": lambda m: {}
        },
        "undo": {
            "keywords": ["undo"],
            "patterns": [
                r"undo",
            ],
            "extractor": lambda m: {}
        },
        "redo": {
            "keywords": ["redo"],
            "patterns": [
                r"redo",
            ],
            "extractor": lambda m: {}
        },
        "save": {
            "keywords": ["save file", "save this"],
            "patterns": [
                r"save\s+(?:the\s+)?(?:file)?",
                r"save\s+this",
            ],
            "extractor": lambda m: {}
        },
        "find": {
            "keywords": ["find", "search in"],
            "patterns": [
                r"find\s+(?:in\s+)?(?:page\s+)?(.+)",
                r"search\s+(?:for\s+)?(?:in\s+page\s+)?(.+)",
            ],
            "extractor": lambda m: {"query": m.group(1).strip() if m.lastindex >= 1 else ""}
        },
    }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FUZZY PHRASE MATCHING - Common variations of commands
    # ═══════════════════════════════════════════════════════════════════════════
    FUZZY_PHRASES = {
        # Volume
        "turn up the volume": ("increase_volume", {}),
        "turn down the volume": ("decrease_volume", {}),
        "make it louder": ("increase_volume", {}),
        "make it quieter": ("decrease_volume", {}),
        "silence the audio": ("mute_system_volume", {}),
        
        # Brightness
        "make it brighter": ("increase_brightness", {}),
        "make it darker": ("decrease_brightness", {}),
        "dim the screen": ("decrease_brightness", {}),
        "brighten the screen": ("increase_brightness", {}),
        
        # Common questions
        "what time is it": ("get_time", {}),
        "what's the time": ("get_time", {}),
        "what is the date": ("get_date", {}),
        "what's today's date": ("get_date", {}),
        
        # System
        "lock the computer": ("lock_workstation", {}),
        "lock my pc": ("lock_workstation", {}),
        "take a screenshot": ("take_screenshot", {}),
        "capture the screen": ("take_screenshot", {}),
        "empty the recycle bin": ("empty_recycle_bin", {}),
        "clear the trash": ("empty_recycle_bin", {}),
        
        # Apps
        "open file manager": ("open_file_explorer", {}),
        "open my files": ("open_file_explorer", {}),
        "open the camera": ("open_camera_app", {}),
    }
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for speed"""
        for func_name, config in self.FUNCTION_REGISTRY.items():
            config["compiled_patterns"] = [
                re.compile(p, re.IGNORECASE) 
                for p in config.get("patterns", [])
            ]
    
    def classify(self, command: str, context: Optional[Any] = None) -> RouteResult:
        """
        Classify user command locally - NO LLM CALLS.
        
        Returns RouteResult with confidence score indicating
        whether to execute locally or forward to Gemini.
        
        Routing:
        - confidence >= 0.85: Execute locally
        - confidence 0.50-0.85: Ask Gemini for intent only
        - confidence < 0.50: Full Gemini reasoning
        """
        command_lower = command.lower().strip()
        
        # ═══════════════════════════════════════════════════════════════
        # CHECK 1: Is this a conversation/question?
        # ═══════════════════════════════════════════════════════════════
        for trigger in self.CONVERSATION_TRIGGERS:
            if command_lower.startswith(trigger):
                return RouteResult(
                    confidence=0.95,
                    is_conversation=True,
                    match_type="conversation",
                    raw_command=command
                )
        
        # ═══════════════════════════════════════════════════════════════
        # CHECK 2: Pattern match with argument extraction (highest priority)
        # ═══════════════════════════════════════════════════════════════
        for func_name, config in self.FUNCTION_REGISTRY.items():
            for pattern in config.get("compiled_patterns", []):
                match = pattern.search(command_lower)
                if match:
                    try:
                        args = config.get("extractor", lambda m: {})(match)
                        return RouteResult(
                            confidence=0.95,
                            function=func_name,
                            args=args,
                            match_type="pattern",
                            raw_command=command
                        )
                    except Exception as e:
                        logging.warning(f"Extractor error for {func_name}: {e}")
                        continue
        
        # ═══════════════════════════════════════════════════════════════
        # CHECK 3: Keyword match (good confidence)
        # ═══════════════════════════════════════════════════════════════
        for func_name, config in self.FUNCTION_REGISTRY.items():
            for keyword in config.get("keywords", []):
                if keyword in command_lower:
                    # Keyword found but no pattern match - medium confidence
                    return RouteResult(
                        confidence=0.75,
                        function=func_name,
                        args={},
                        match_type="keyword",
                        raw_command=command
                    )
        
        # ═══════════════════════════════════════════════════════════════
        # CHECK 4: Fuzzy phrase matching
        # ═══════════════════════════════════════════════════════════════
        if FUZZY_AVAILABLE:
            best_match = process.extractOne(
                command_lower,
                list(self.FUZZY_PHRASES.keys()),
                scorer=fuzz.ratio
            )
            
            if best_match and best_match[1] >= 75:  # 75% similarity
                phrase = best_match[0]
                func_name, args = self.FUZZY_PHRASES[phrase]
                confidence = best_match[1] / 100.0
                return RouteResult(
                    confidence=confidence,
                    function=func_name,
                    args=args,
                    match_type="fuzzy",
                    raw_command=command
                )
        
        # ═══════════════════════════════════════════════════════════════
        # CHECK 5: Partial keyword matching (lower confidence)
        # ═══════════════════════════════════════════════════════════════
        words = command_lower.split()
        for func_name, config in self.FUNCTION_REGISTRY.items():
            for keyword in config.get("keywords", []):
                keyword_words = keyword.split()
                # Check if any keyword word is in command
                if any(kw in words for kw in keyword_words):
                    return RouteResult(
                        confidence=0.50,
                        function=func_name,
                        args={},
                        match_type="partial",
                        raw_command=command
                    )
        
        # ═══════════════════════════════════════════════════════════════
        # NO LOCAL MATCH - needs Gemini
        # ═══════════════════════════════════════════════════════════════
        return RouteResult(
            confidence=0.0,
            match_type="none",
            raw_command=command
        )
    
    def get_function_mapping(self, intent_name: str) -> Optional[str]:
        """
        Map an intent name to the actual function name in windows_system_utils.
        This handles variations and aliases.
        """
        # Direct mapping for most cases
        direct_map = {
            "set_system_volume": "set_system_volume",
            "mute_system_volume": "mute_system_volume",
            "unmute_system_volume": "unmute_system_volume",
            "increase_volume": "set_system_volume",  # Will need adjustment logic
            "decrease_volume": "set_system_volume",
            "set_brightness": "set_brightness",
            "increase_brightness": "adjust_brightness",
            "decrease_brightness": "adjust_brightness",
            "open_application": "open_application",  
            "close_application": "close_application",
            "open_file_explorer": "open_file_explorer",
            "take_screenshot": "take_screenshot",
            "open_camera_app": "open_camera_app",
            "lock_workstation": "lock_workstation",
            "restart_explorer": "restart_explorer",
            "empty_recycle_bin": "empty_recycle_bin",
            "night_light_on": "toggle_night_light",
            "night_light_off": "toggle_night_light",
            "airplane_mode_on": "toggle_airplane_mode_advanced",
            "airplane_mode_off": "toggle_airplane_mode_advanced",
            "hide_desktop_icons": "hide_desktop_icons",
            "show_desktop_icons": "show_desktop_icons",
            "play_youtube_video_ultra_direct": "play_youtube_video_ultra_direct",
            "create_folder": "create_folder",
            "create_powerpoint_presentation": "create_powerpoint_presentation",
            "create_ai_news_file": "create_ai_news_file",
        }
        
        return direct_map.get(intent_name)


# Global instance
intent_router = IntentRouter()


def get_intent_router() -> IntentRouter:
    """Get the global intent router"""
    return intent_router


def classify_command(command: str) -> RouteResult:
    """Convenience function for classifying a command"""
    return intent_router.classify(command)
