"""
AURA v2 - Core Control Loop
The main orchestrator that ties together all components.

Architecture:
┌─────────────────────────────────────────────────────────────────────────┐
│                         AURA v2 CONTROL LOOP                            │
├─────────────────────────────────────────────────────────────────────────┤
│  SLEEPING ──▶ Wake Word ──▶ LISTENING ──▶ PROCESSING ──▶ SPEAKING     │
│      ▲                                                        │         │
│      └────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘

Token Savings:
- Local commands: 0 tokens (direct execution)
- Intent-only mode: ~100 tokens (minimal Gemini call)
- Full reasoning: ~500 tokens (only when needed)
- Chat mode: ~300 tokens (conversational)
"""

import logging
import time
import threading
from typing import Optional
from dataclasses import dataclass

# AURA v2 Components
from local_context import LocalContext, AuraState, AuraMode, get_context
from response_generator import ResponseGenerator, get_response_generator
from intent_router import IntentRouter, RouteResult, get_intent_router
from function_executor import FunctionExecutor, ExecutionResult, get_function_executor
from wake_word_detector import KeywordWakeDetector, check_wake_word, extract_command_after_wake

# TTS
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    logging.warning("pyttsx3 not available. Install with: pip install pyttsx3")

# Existing AI client for Gemini
try:
    from ai_client import ai_client as gemini_client
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("Gemini AI client not available")


class AuraCore:
    """
    AURA v2 Core - The main control loop.
    
    This orchestrates:
    1. Wake word detection (hands-free activation)
    2. Speech recognition (voice input)
    3. Intent routing (local classification)
    4. Function execution (task completion)
    5. TTS output (voice feedback)
    6. Gemini integration (fallback reasoning)
    """
    
    def __init__(self, user_name: str = "Sir"):
        # Initialize components
        self.context = get_context()
        self.context.user_name = user_name
        
        self.response_gen = get_response_generator()
        self.response_gen.user_name = user_name
        
        self.intent_router = get_intent_router()
        self.executor = get_function_executor()
        self.wake_detector = KeywordWakeDetector()
        
        # TTS Engine
        self._tts_engine = None
        self._init_tts()
        
        # Gemini (lazy load)
        self._gemini = None
        
        # State
        self.is_running = False
        self._command_queue = []
        
        # Stats
        self.stats = {
            "local_commands": 0,
            "gemini_intent": 0,
            "gemini_full": 0,
            "gemini_chat": 0,
            "tokens_saved": 0,
        }
        
        logging.info("AuraCore initialized")
    
    def _init_tts(self):
        """Initialize text-to-speech engine"""
        if TTS_AVAILABLE:
            try:
                self._tts_engine = pyttsx3.init()
                # Configure voice
                voices = self._tts_engine.getProperty('voices')
                # Try to use a female voice (usually index 1)
                if len(voices) > 1:
                    self._tts_engine.setProperty('voice', voices[1].id)
                self._tts_engine.setProperty('rate', 175)  # Speed
                self._tts_engine.setProperty('volume', 0.9)
                logging.info("TTS engine initialized")
            except Exception as e:
                logging.error(f"TTS init error: {e}")
                self._tts_engine = None
    
    def speak(self, text: str, blocking: bool = True):
        """
        Speak text using TTS.
        
        Args:
            text: Text to speak
            blocking: Wait for speech to complete
        """
        if not text:
            return
        
        logging.info(f"AURA: {text}")
        
        if self._tts_engine:
            try:
                if blocking:
                    self._tts_engine.say(text)
                    self._tts_engine.runAndWait()
                else:
                    # Non-blocking speech in thread
                    def speak_thread():
                        self._tts_engine.say(text)
                        self._tts_engine.runAndWait()
                    threading.Thread(target=speak_thread, daemon=True).start()
            except Exception as e:
                logging.error(f"TTS error: {e}")
    
    @property
    def gemini(self):
        """Lazy load Gemini client"""
        if self._gemini is None and GEMINI_AVAILABLE:
            self._gemini = gemini_client
        return self._gemini
    
    def process_command(self, command: str) -> str:
        """
        Process a voice command through the full pipeline.
        
        Pipeline:
        1. Local intent routing
        2. If high confidence → execute locally
        3. If medium confidence → Gemini intent-only
        4. If low confidence → Gemini full reasoning
        5. If conversation → Gemini chat mode
        
        Returns:
            Response text to speak
        """
        self.context.current_state = AuraState.PROCESSING
        command = command.strip()
        
        if not command:
            return ""
        
        logging.info(f"Processing: {command}")
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Local Intent Classification (FREE)
        # ═══════════════════════════════════════════════════════════════════
        route_result = self.intent_router.classify(command, self.context)
        
        logging.info(f"Route: {route_result.match_type}, conf={route_result.confidence:.2f}, func={route_result.function}")
        
        # ═══════════════════════════════════════════════════════════════════
        # ROUTE A: Conversation Mode → Gemini Chat
        # ═══════════════════════════════════════════════════════════════════
        if route_result.is_conversation:
            self.context.current_mode = AuraMode.CONVERSATION
            return self._handle_conversation(command)
        
        # ═══════════════════════════════════════════════════════════════════
        # ROUTE B: High Confidence → Local Execution (0 tokens!)
        # ═══════════════════════════════════════════════════════════════════
        if route_result.confidence >= 0.85 and route_result.function:
            return self._execute_local(route_result)
        
        # ═══════════════════════════════════════════════════════════════════
        # ROUTE C: Medium Confidence → Gemini Intent-Only (~100 tokens)
        # ═══════════════════════════════════════════════════════════════════
        if route_result.confidence >= 0.50:
            return self._handle_gemini_intent(command, route_result)
        
        # ═══════════════════════════════════════════════════════════════════
        # ROUTE D: Low Confidence → Gemini Full Reasoning (~500 tokens)
        # ═══════════════════════════════════════════════════════════════════
        return self._handle_gemini_full(command)
    
    def _execute_local(self, route_result: RouteResult) -> str:
        """Execute command locally without Gemini (0 tokens)"""
        self.stats["local_commands"] += 1
        self.stats["tokens_saved"] += 500  # Estimated tokens saved
        
        logging.info(f"LOCAL EXEC: {route_result.function} (saved ~500 tokens)")
        
        # Execute the function
        result = self.executor.execute(
            function_name=route_result.function,
            args=route_result.args
        )
        
        # Record in context
        self.context.record_command(
            command=route_result.raw_command,
            function=route_result.function,
            success=result.success,
            result=str(result.result) if result.success else result.error
        )
        
        # Generate local response
        response = self.response_gen.confirmation(
            result=result.success,
            context={
                "function": route_result.function,
                "value": route_result.args.get("level"),
                "app": route_result.args.get("app_name"),
                "name": route_result.args.get("folder_name"),
            }
        )
        
        return response
    
    def _handle_gemini_intent(self, command: str, route_result: RouteResult) -> str:
        """Use Gemini for intent classification only (~100 tokens)"""
        self.stats["gemini_intent"] += 1
        
        logging.info(f"GEMINI INTENT: {command}")
        
        if not self.gemini:
            # Fallback to local execution with lower confidence
            if route_result.function:
                return self._execute_local(route_result)
            return self.response_gen.not_understood()
        
        try:
            # Build minimal intent prompt
            prompt = self._build_intent_prompt(command)
            
            response = self.gemini.client.models.generate_content(
                model="gemini-2.0-flash",  # Fastest/cheapest
                contents=prompt,
                generation_config={
                    "max_output_tokens": 100,  # Minimal
                    "temperature": 0.1,        # Deterministic
                }
            )
            
            # Parse intent response
            import json
            intent_text = response.text.strip()
            
            # Try to extract JSON
            if "{" in intent_text:
                start = intent_text.find("{")
                end = intent_text.rfind("}") + 1
                intent_json = json.loads(intent_text[start:end])
                
                if intent_json.get("function"):
                    # Execute the identified function
                    result = self.executor.execute(
                        function_name=intent_json["function"],
                        args=intent_json.get("args", {})
                    )
                    
                    self.context.record_command(
                        command=command,
                        function=intent_json["function"],
                        success=result.success
                    )
                    
                    return self.response_gen.confirmation(result.success)
                
                elif intent_json.get("intent") == "conversation":
                    return self._handle_conversation(command)
            
            # Couldn't parse, treat as conversation
            return self._handle_conversation(command)
            
        except Exception as e:
            logging.error(f"Gemini intent error: {e}")
            # Fallback to local if possible
            if route_result.function:
                return self._execute_local(route_result)
            return self.response_gen.failure()
    
    def _handle_gemini_full(self, command: str) -> str:
        """Use Gemini for full code generation (~500 tokens)"""
        self.stats["gemini_full"] += 1
        
        logging.info(f"GEMINI FULL: {command}")
        
        if not self.gemini:
            return self.response_gen.not_understood()
        
        try:
            # Use existing AI client for full code generation
            code = self.gemini.generate_code(command, context={
                "filename": self.context.last_command,
            })
            
            if code:
                # Execute the generated code
                result = self.executor.execute_raw(code)
                
                self.context.record_command(
                    command=command,
                    function="generated_code",
                    success=result.success
                )
                
                return self.response_gen.confirmation(result.success)
            
            return self.response_gen.failure()
            
        except Exception as e:
            logging.error(f"Gemini full error: {e}")
            return self.response_gen.failure()
    
    def _handle_conversation(self, message: str) -> str:
        """Handle conversational messages with Gemini (~300 tokens)"""
        self.stats["gemini_chat"] += 1
        
        logging.info(f"GEMINI CHAT: {message}")
        
        if not self.gemini:
            return "I'm sorry, my conversation system is offline right now."
        
        try:
            prompt = f"""You are Aura, a helpful AI assistant with a warm, professional personality.
Be concise (under 50 words unless asked for detail).

User: {message}"""
            
            response = self.gemini.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                generation_config={
                    "max_output_tokens": 150,
                    "temperature": 0.7,
                }
            )
            
            return response.text.strip()
            
        except Exception as e:
            logging.error(f"Gemini chat error: {e}")
            return "I'm having trouble connecting right now."
    
    def _build_intent_prompt(self, command: str) -> str:
        """Build minimal prompt for intent classification"""
        # List of available functions (abbreviated)
        functions = [
            "set_system_volume(level)", "mute_system_volume()", "unmute_system_volume()",
            "set_brightness(level)", "adjust_brightness(change)",
            "open_application(app_name)", "close_application(app_name)",
            "take_screenshot()", "open_camera_app()", "lock_workstation()",
            "hide_desktop_icons()", "show_desktop_icons()",
            "toggle_night_light(enable)", "toggle_airplane_mode_advanced(enable)",
            "play_youtube_video_ultra_direct(search_term)",
            "create_folder(folder_name)", "create_powerpoint_presentation(topic)",
        ]
        
        return f"""Classify this command. Available functions: {', '.join(functions)}

Command: "{command}"

Respond with JSON only:
{{"intent": "function|conversation|unknown", "function": "function_name_or_null", "args": {{}}, "confidence": 0.0-1.0}}"""
    
    def greet(self):
        """Speak greeting on startup"""
        greeting = self.response_gen.greeting()
        self.speak(greeting)
    
    def get_stats(self) -> dict:
        """Get performance statistics"""
        total = (self.stats["local_commands"] + self.stats["gemini_intent"] + 
                 self.stats["gemini_full"] + self.stats["gemini_chat"])
        
        return {
            **self.stats,
            "total_commands": total,
            "local_percentage": (self.stats["local_commands"] / total * 100) if total > 0 else 0,
            "estimated_savings": f"~{self.stats['tokens_saved']} tokens",
        }
    
    def print_stats(self):
        """Print performance statistics"""
        stats = self.get_stats()
        print("\n" + "="*50)
        print("AURA v2 Performance Statistics")
        print("="*50)
        print(f"Local commands:     {stats['local_commands']} ({stats['local_percentage']:.1f}%)")
        print(f"Gemini intent-only: {stats['gemini_intent']}")
        print(f"Gemini full:        {stats['gemini_full']}")
        print(f"Gemini chat:        {stats['gemini_chat']}")
        print(f"Total commands:     {stats['total_commands']}")
        print(f"Estimated savings:  {stats['estimated_savings']}")
        print("="*50 + "\n")


# Global instance
aura_core = None


def get_aura_core() -> AuraCore:
    """Get or create the global AuraCore instance"""
    global aura_core
    if aura_core is None:
        aura_core = AuraCore()
    return aura_core


def process_voice_command(command: str) -> str:
    """Process a voice command and return the response"""
    return get_aura_core().process_command(command)


def speak(text: str):
    """Speak text using AURA's voice"""
    get_aura_core().speak(text)


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO / TEST FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def demo():
    """Demo the AURA v2 system"""
    print("\n" + "="*60)
    print("AURA v2 - Hands-Free Voice Assistant Demo")
    print("="*60 + "\n")
    
    core = get_aura_core()
    core.greet()
    
    # Test commands
    test_commands = [
        "set brightness to 50",          # Should route locally (0 tokens)
        "turn up the volume",             # Should route locally (0 tokens)
        "mute",                           # Should route locally (0 tokens)
        "open chrome",                    # Should route locally (0 tokens)
        "take a screenshot",              # Should route locally (0 tokens)
        "what time is it",                # Should route locally (0 tokens)
        "what is machine learning",       # Should go to Gemini chat
        "play despacito on youtube",      # Should route locally (0 tokens)
    ]
    
    print("Testing commands:\n")
    
    for cmd in test_commands:
        print(f"\n▶ Command: \"{cmd}\"")
        response = core.process_command(cmd)
        print(f"◀ Response: \"{response}\"")
        time.sleep(0.5)
    
    core.print_stats()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo()
