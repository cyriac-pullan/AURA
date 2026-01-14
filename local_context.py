"""
AURA v2 - Local Context Memory
Maintains session state locally without consuming LLM tokens.
Only passed to Gemini when truly needed.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class AuraState(Enum):
    """Current operational state of AURA"""
    SLEEPING = "sleeping"           # Waiting for wake word
    LISTENING = "listening"         # Active listening after wake
    PROCESSING = "processing"       # Executing command
    SPEAKING = "speaking"           # TTS output in progress


class AuraMode(Enum):
    """Interaction mode - affects how AURA responds"""
    COMMAND = "command"             # Fast, minimal speech, efficient
    CONVERSATION = "conversation"   # Full chat allowed, more verbose


@dataclass
class LocalContext:
    """
    Local memory for AURA - stored in RAM, never sent to LLM unless needed.
    This dramatically reduces token usage by keeping state locally.
    """
    # User identification
    user_name: str = "Sir"
    
    # Current session state
    last_command: str = ""
    last_result: str = ""
    last_function: str = ""
    last_error: str = ""
    
    # Mode and state
    current_mode: AuraMode = AuraMode.COMMAND
    current_state: AuraState = AuraState.SLEEPING
    
    # Session history (kept minimal)
    session_commands: List[str] = field(default_factory=list)
    session_start_time: datetime = field(default_factory=datetime.now)
    command_count: int = 0
    success_count: int = 0
    
    # Active app tracking
    active_app: str = ""
    active_window: str = ""
    
    # Preferences (loaded from config)
    voice_enabled: bool = True
    wake_word: str = "aura"
    confirmation_style: str = "brief"  # brief, detailed, silent
    
    def record_command(self, command: str, function: str = "", success: bool = True, result: str = ""):
        """Record a command execution"""
        self.last_command = command
        self.last_function = function
        self.last_result = result if success else ""
        self.last_error = "" if success else result
        
        self.command_count += 1
        if success:
            self.success_count += 1
        
        # Keep last 10 commands only
        self.session_commands.append(command)
        if len(self.session_commands) > 10:
            self.session_commands.pop(0)
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get a brief summary for Gemini context (minimal tokens)"""
        return {
            "user": self.user_name,
            "mode": self.current_mode.value,
            "last_cmd": self.last_command[:50] if self.last_command else None,
            "cmd_count": self.command_count,
            "session_mins": int((datetime.now() - self.session_start_time).seconds / 60)
        }
    
    def to_gemini_context(self) -> str:
        """Format context for Gemini prompt (only when needed)"""
        return f"""User: {self.user_name}
Mode: {self.current_mode.value}
Last command: {self.last_command[:100] if self.last_command else 'None'}
Session commands: {self.command_count}"""
    
    def reset_session(self):
        """Reset session state (but keep user preferences)"""
        self.last_command = ""
        self.last_result = ""
        self.last_function = ""
        self.last_error = ""
        self.session_commands = []
        self.session_start_time = datetime.now()
        self.command_count = 0
        self.success_count = 0
        self.current_state = AuraState.SLEEPING
        self.current_mode = AuraMode.COMMAND


# Global context instance
context = LocalContext()


def get_context() -> LocalContext:
    """Get the global context instance"""
    return context


def reset_context():
    """Reset the global context"""
    global context
    context = LocalContext()
    return context
