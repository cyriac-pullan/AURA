"""
AURA v2 - Local Response Generator
Generates personality responses WITHOUT calling LLM.
All confirmations and acknowledgments are handled locally for zero token cost.
"""

import random
from datetime import datetime
from typing import Any, Optional, Dict


class ResponseGenerator:
    """
    Generate AURA's personality responses WITHOUT calling LLM.
    This is critical for cost savings - all routine responses are free.
    """
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ACKNOWLEDGMENTS - When AURA hears the wake word
    # ═══════════════════════════════════════════════════════════════════════════
    ACKNOWLEDGMENTS = [
        "Yes?",
        "I'm here.",
        "Listening.",
        "What can I do for you?",
        "At your service.",
        "Go ahead.",
        "Yes, {user}?",
        "Ready.",
        "I'm listening.",
    ]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SUCCESS CONFIRMATIONS - After completing a task
    # ═══════════════════════════════════════════════════════════════════════════
    CONFIRMATIONS_SUCCESS = [
        "Done.",
        "Done, {user}.",
        "On it.",
        "Consider it done.",
        "Right away.",
        "Executing now.",
        "Got it.",
        "Completed.",
        "All set.",
        "Task complete.",
        "Finished.",
    ]
    
    # Brief confirmations for command mode
    CONFIRMATIONS_BRIEF = [
        "Done.",
        "Got it.",
        "Done, {user}.",
        "Okay.",
    ]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTEXTUAL CONFIRMATIONS - With specific values
    # ═══════════════════════════════════════════════════════════════════════════
    CONFIRMATIONS_CONTEXTUAL = {
        "brightness": [
            "Brightness set to {value}%.",
            "Screen brightness is now {value}%.",
            "Adjusted brightness to {value}%.",
        ],
        "volume": [
            "Volume set to {value}%.",
            "Audio level is now {value}%.",
            "Volume adjusted to {value}%.",
        ],
        "mute": [
            "Audio muted.",
            "Sound is muted.",
            "Muted.",
        ],
        "unmute": [
            "Audio unmuted.",
            "Sound restored.",
            "Unmuted.",
        ],
        "app_open": [
            "{app} is now open.",
            "Opening {app}.",
            "Launched {app}.",
        ],
        "app_close": [
            "{app} closed.",
            "Closing {app}.",
            "Terminated {app}.",
        ],
        "folder": [
            "Folder created: {name}.",
            "Created folder {name}.",
        ],
        "screenshot": [
            "Screenshot captured.",
            "Screen captured.",
            "Screenshot saved.",
        ],
        "youtube": [
            "Opening YouTube.",
            "Playing on YouTube.",
            "Searching YouTube for {query}.",
        ],
        "spotify": [
            "Opening Spotify.",
            "Playing on Spotify.",
            "Searching Spotify for {query}.",
        ],
        "google": [
            "Searching Google.",
            "Looking that up.",
            "Googling {query}.",
        ],
        "weather": [
            "Showing weather.",
            "Getting weather info.",
            "Opening weather for {location}.",
        ],
        "news": [
            "Opening Google News.",
            "Getting the latest news.",
            "Here are the headlines.",
        ],
        "email": [
            "Opening Gmail.",
            "Checking your mail.",
            "Loading email.",
        ],
        "timer": [
            "Timer set for {duration} {unit}.",
            "I'll alert you in {duration} {unit}.",
            "Countdown started.",
        ],
        "media": [
            "Done.",
            "Toggled.",
        ],
        "note": [
            "Note saved.",
            "Got it, I'll remember that.",
            "Noted.",
        ],
        "time": [
            "The time is {value}.",
            "It's {value}.",
        ],
        "date": [
            "Today is {value}.",
            "It's {value}.",
        ],
        "website": [
            "Opening {url}.",
            "Loading {url}.",
        ],
    }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FAILURES - When something goes wrong
    # ═══════════════════════════════════════════════════════════════════════════
    FAILURES = [
        "I couldn't do that.",
        "Something went wrong.",
        "That didn't work, {user}.",
        "I ran into an issue.",
        "Failed to complete that.",
        "I'm sorry, that failed.",
        "Unable to complete that task.",
    ]
    
    FAILURES_SPECIFIC = {
        "not_found": [
            "I couldn't find that.",
            "That wasn't found.",
            "Unable to locate that.",
        ],
        "permission": [
            "I don't have permission for that.",
            "Access denied.",
            "Insufficient permissions.",
        ],
        "network": [
            "Network issue detected.",
            "Connection problem.",
            "Unable to reach the network.",
        ],
        "unknown": [
            "I'm not sure how to do that.",
            "I don't understand that command.",
            "Could you rephrase that?",
        ],
    }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # THINKING/PROCESSING - While working on something
    # ═══════════════════════════════════════════════════════════════════════════
    THINKING = [
        "Working on it...",
        "Processing...",
        "One moment...",
        "Let me handle that...",
        "On it...",
    ]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GREETINGS - Time-based greetings
    # ═══════════════════════════════════════════════════════════════════════════
    GREETINGS = {
        "morning": [
            "Good morning, {user}. Aura is online and ready.",
            "Good morning. How can I assist you today?",
            "Morning, {user}. Systems are operational.",
        ],
        "afternoon": [
            "Good afternoon, {user}. Aura at your service.",
            "Good afternoon. Ready to assist.",
            "Afternoon, {user}. What do you need?",
        ],
        "evening": [
            "Good evening, {user}. Aura is online.",
            "Good evening. How may I help?",
            "Evening, {user}. Systems ready.",
        ],
        "night": [
            "Good evening, {user}. Aura is standing by.",
            "Hello, {user}. Working late?",
            "Aura online. Ready when you are.",
        ],
    }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GOODBYES - When shutting down or user leaves
    # ═══════════════════════════════════════════════════════════════════════════
    GOODBYES = [
        "Shutting down. Goodbye, {user}.",
        "Going offline. Take care.",
        "Signing off. Until next time.",
        "Goodbye, {user}. Aura going to sleep.",
        "Standing down. Have a good one.",
    ]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS REPORTS - When asked about status
    # ═══════════════════════════════════════════════════════════════════════════
    STATUS_REPORTS = [
        "All systems operational, {user}.",
        "Everything is running smoothly.",
        "Status: All green. Ready for commands.",
        "Systems nominal. Standing by.",
    ]
    
    def __init__(self, user_name: str = "Sir", confirmation_style: str = "brief"):
        self.user_name = user_name
        self.confirmation_style = confirmation_style  # brief, detailed, silent
    
    def _format(self, text: str, **kwargs) -> str:
        """Format text with user name and other variables"""
        kwargs.setdefault("user", self.user_name)
        try:
            return text.format(**kwargs)
        except KeyError:
            return text.replace("{user}", self.user_name)
    
    def acknowledgment(self) -> str:
        """Get a random acknowledgment for wake word detection"""
        return self._format(random.choice(self.ACKNOWLEDGMENTS))
    
    def confirmation(self, result: Any = None, context: Optional[Dict] = None) -> str:
        """
        Get a confirmation message after completing a task.
        
        Args:
            result: The result of the operation (True/False/dict/str)
            context: Optional context with details (function, value, app, etc.)
        """
        context = context or {}
        
        # Handle failure cases
        if result is False:
            error_type = context.get("error_type", "general")
            if error_type in self.FAILURES_SPECIFIC:
                return self._format(random.choice(self.FAILURES_SPECIFIC[error_type]))
            return self._format(random.choice(self.FAILURES))
        
        # Handle contextual confirmations
        if context:
            func = context.get("function", "")
            
            # Brightness
            if "brightness" in func and "value" in context:
                return self._format(
                    random.choice(self.CONFIRMATIONS_CONTEXTUAL["brightness"]),
                    value=context["value"]
                )
            
            # Volume
            if "volume" in func and "value" in context:
                return self._format(
                    random.choice(self.CONFIRMATIONS_CONTEXTUAL["volume"]),
                    value=context["value"]
                )
            
            # Mute/Unmute
            if "mute" in func:
                key = "unmute" if "unmute" in func else "mute"
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL[key]))
            
            # App operations
            if "open" in func and "app" in context:
                return self._format(
                    random.choice(self.CONFIRMATIONS_CONTEXTUAL["app_open"]),
                    app=context["app"]
                )
            if "close" in func and "app" in context:
                return self._format(
                    random.choice(self.CONFIRMATIONS_CONTEXTUAL["app_close"]),
                    app=context["app"]
                )
            
            # Screenshot
            if "screenshot" in func:
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["screenshot"]))
            
            # YouTube
            if "youtube" in func:
                query = context.get("query", "")
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["youtube"]), query=query)
            
            # Spotify
            if "spotify" in func:
                query = context.get("query", "")
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["spotify"]), query=query)
            
            # Google Search
            if "google" in func:
                query = context.get("query", "")
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["google"]), query=query)
            
            # Weather
            if "weather" in func:
                location = context.get("location", "your area")
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["weather"]), location=location)
            
            # News
            if "news" in func:
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["news"]))
            
            # Email
            if "email" in func:
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["email"]))
            
            # Timer
            if "timer" in func:
                duration = context.get("duration", "")
                unit = context.get("unit", "minutes")
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["timer"]), duration=duration, unit=unit)
            
            # Media controls
            if "media" in func:
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["media"]))
            
            # Notes
            if "note" in func:
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["note"]))
            
            # Time
            if func == "get_time" and "value" in context:
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["time"]), value=context["value"])
            
            # Date
            if func == "get_date" and "value" in context:
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["date"]), value=context["value"])
            
            # Website
            if "website" in func and "url" in context:
                return self._format(random.choice(self.CONFIRMATIONS_CONTEXTUAL["website"]), url=context["url"])
            
            # Folder creation
            if "folder" in func and "name" in context:
                return self._format(
                    random.choice(self.CONFIRMATIONS_CONTEXTUAL["folder"]),
                    name=context["name"]
                )
        
        # Default success confirmation based on style
        if self.confirmation_style == "brief":
            return self._format(random.choice(self.CONFIRMATIONS_BRIEF))
        elif self.confirmation_style == "silent":
            return ""
        else:
            return self._format(random.choice(self.CONFIRMATIONS_SUCCESS))
    
    def thinking(self) -> str:
        """Get a response while processing"""
        return self._format(random.choice(self.THINKING))
    
    def greeting(self) -> str:
        """Get a time-appropriate greeting"""
        hour = datetime.now().hour
        
        if 5 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 17:
            period = "afternoon"
        elif 17 <= hour < 21:
            period = "evening"
        else:
            period = "night"
        
        return self._format(random.choice(self.GREETINGS[period]))
    
    def goodbye(self) -> str:
        """Get a farewell message"""
        return self._format(random.choice(self.GOODBYES))
    
    def failure(self, error_type: str = "general") -> str:
        """Get a failure message"""
        if error_type in self.FAILURES_SPECIFIC:
            return self._format(random.choice(self.FAILURES_SPECIFIC[error_type]))
        return self._format(random.choice(self.FAILURES))
    
    def status(self) -> str:
        """Get a status report"""
        return self._format(random.choice(self.STATUS_REPORTS))
    
    def not_understood(self) -> str:
        """When command isn't understood"""
        return self._format(random.choice(self.FAILURES_SPECIFIC["unknown"]))


# Global instance
response_generator = ResponseGenerator()


def get_response_generator() -> ResponseGenerator:
    """Get the global response generator"""
    return response_generator


def set_user_name(name: str):
    """Update the user name for responses"""
    response_generator.user_name = name
