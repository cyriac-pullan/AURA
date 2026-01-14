"""
AURA v2 - Widget Integration Bridge
Integrates the new AURA v2 architecture with the existing floating widget.
Drop-in replacement for the current processing pipeline.
"""

import logging
from typing import Optional, Dict, Any, Tuple

# AURA v2 Components
from local_context import get_context, AuraState, AuraMode
from response_generator import get_response_generator
from intent_router import get_intent_router, RouteResult
from function_executor import get_function_executor
from wake_word_detector import check_wake_word, extract_command_after_wake


class AuraV2Bridge:
    """
    Bridge between AURA v2 and the existing floating widget.
    
    This allows the widget to use the new intelligent routing
    while maintaining backward compatibility.
    
    Usage in aura_widget.py:
        from aura_v2_bridge import aura_bridge
        
        # In ProcessingThread.run():
        response, success, used_gemini = aura_bridge.process(message, context)
    """
    
    def __init__(self):
        self.context = get_context()
        self.response_gen = get_response_generator()
        self.intent_router = get_intent_router()
        self.executor = get_function_executor()
        
        # Gemini client (lazy load)
        self._ai_client = None
        
        # Stats
        self.stats = {
            "local_commands": 0,
            "gemini_intent": 0,
            "gemini_full": 0,
            "gemini_chat": 0,
            "tokens_saved": 0,
        }
        
        logging.info("AuraV2Bridge initialized")
    
    @property
    def ai_client(self):
        """Lazy load AI client"""
        if self._ai_client is None:
            try:
                from ai_client import ai_client
                self._ai_client = ai_client
            except Exception as e:
                logging.error(f"Could not load AI client: {e}")
        return self._ai_client
    
    def process(self, command: str, context: Dict[str, Any] = None) -> Tuple[str, bool, bool]:
        """
        Process a command using AURA v2 intelligent routing.
        
        v2.1: Always fallback to LLM if local execution fails (like v1 behavior)
        
        Args:
            command: The user's voice command
            context: Optional context dict (filename, etc.)
            
        Returns:
            Tuple of (response_text, success, used_gemini)
        """
        command = command.strip()
        if not command:
            return "", False, False
        
        logging.info(f"AuraV2Bridge processing: {command}")
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 1: Local Intent Classification (FREE)
        # ═══════════════════════════════════════════════════════════════
        route_result = self.intent_router.classify(command, self.context)
        
        logging.info(f"Route result: {route_result.match_type}, conf={route_result.confidence:.2f}")
        
        # ═══════════════════════════════════════════════════════════════
        # ROUTE A: Conversation → Gemini Chat
        # ═══════════════════════════════════════════════════════════════
        if route_result.is_conversation:
            self.stats["gemini_chat"] += 1
            return self._handle_conversation(command)
        
        # ═══════════════════════════════════════════════════════════════
        # v2.1 UNIFIED ROUTING: Try local first, ALWAYS fallback to LLM
        # This restores v1-like behavior where any command can work
        # ═══════════════════════════════════════════════════════════════
        
        # If we have a function match (any confidence), try local first
        if route_result.function and route_result.confidence >= 0.50:
            logging.info(f"Trying local execution: {route_result.function}")
            result = self._execute_local(route_result)
            if result[1]:  # success
                self.stats["local_commands"] += 1
                self.stats["tokens_saved"] += 500
                return result
            else:
                logging.info(f"Local execution failed, falling back to LLM")
        
        # ═══════════════════════════════════════════════════════════════
        # FALLBACK: Use LLM to generate and execute code (v1 behavior)
        # This handles ANY command that local routing can't handle
        # ═══════════════════════════════════════════════════════════════
        logging.info(f"Using LLM fallback for: {command}")
        self.stats["gemini_full"] += 1
        return self._handle_gemini(command, context)
    
    def _execute_local(self, route_result: RouteResult) -> Tuple[str, bool, bool]:
        """Execute command locally (0 tokens)"""
        logging.info(f"LOCAL EXEC: {route_result.function}")
        
        result = self.executor.execute(
            function_name=route_result.function,
            args=route_result.args
        )
        
        # Update context
        self.context.record_command(
            command=route_result.raw_command,
            function=route_result.function,
            success=result.success
        )
        
        # Generate response
        response = self.response_gen.confirmation(
            result=result.success,
            context={
                "function": route_result.function,
                "value": route_result.args.get("level"),
                "app": route_result.args.get("app_name"),
            }
        )
        
        return response, result.success, False  # False = didn't use Gemini
    
    def _handle_gemini(self, command: str, context: Dict = None) -> Tuple[str, bool, bool]:
        """Handle command with Gemini AI"""
        logging.info(f"GEMINI: {command}")
        
        if not self.ai_client:
            return "I'm having trouble connecting to my AI systems.", False, False
        
        try:
            # Use existing AI client for code generation
            code = self.ai_client.generate_code(command, context=context or {})
            
            if code:
                # Execute the generated code
                result = self.executor.execute_raw(code)
                
                self.context.record_command(
                    command=command,
                    function="generated_code",
                    success=result.success
                )
                
                response = self.response_gen.confirmation(result.success)
                return response, result.success, True
            
            return self.response_gen.failure(), False, True
            
        except Exception as e:
            logging.error(f"Gemini error: {e}")
            return self.response_gen.failure(), False, True
    
    def _handle_conversation(self, message: str) -> Tuple[str, bool, bool]:
        """Handle conversational message"""
        logging.info(f"CONVERSATION: {message}")
        
        if not self.ai_client:
            return "I'm having trouble connecting right now.", False, False
        
        try:
            prompt = f"""You are Aura, a helpful AI assistant. Be concise.
            
User: {message}"""
            
            response = self.ai_client.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                generation_config={
                    "max_output_tokens": 150,
                    "temperature": 0.7,
                }
            )
            
            return response.text.strip(), True, True
            
        except Exception as e:
            logging.error(f"Conversation error: {e}")
            return "I'm having trouble with that right now.", False, True
    
    def get_acknowledgment(self) -> str:
        """Get a wake word acknowledgment"""
        return self.response_gen.acknowledgment()
    
    def get_greeting(self) -> str:
        """Get a time-appropriate greeting"""
        return self.response_gen.greeting()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        total = sum([
            self.stats["local_commands"],
            self.stats["gemini_intent"],
            self.stats["gemini_full"],
            self.stats["gemini_chat"],
        ])
        
        return {
            **self.stats,
            "total_commands": total,
            "local_percentage": (self.stats["local_commands"] / total * 100) if total > 0 else 0,
        }
    
    def check_wake_word(self, text: str) -> bool:
        """Check if text contains wake word"""
        return check_wake_word(text)
    
    def extract_command(self, text: str) -> str:
        """Extract command after wake word"""
        return extract_command_after_wake(text)


# Global bridge instance
aura_bridge = AuraV2Bridge()


def process_command(command: str, context: Dict = None) -> Tuple[str, bool, bool]:
    """
    Process a command using AURA v2.
    
    Returns:
        (response, success, used_gemini)
    """
    return aura_bridge.process(command, context)


def get_acknowledgment() -> str:
    """Get a wake word acknowledgment"""
    return aura_bridge.get_acknowledgment()


def get_greeting() -> str:
    """Get a greeting"""
    return aura_bridge.get_greeting()


# ═══════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE IN WIDGET
# ═══════════════════════════════════════════════════════════════════════════════
"""
To integrate AURA v2 into the existing widget, modify ProcessingThread.run() in aura_widget.py:

from aura_v2_bridge import aura_bridge

class ProcessingThread(QThread):
    def run(self):
        try:
            # Use AURA v2 for intelligent routing
            response, success, used_gemini = aura_bridge.process(
                self.message, 
                self.context
            )
            
            self.finished.emit(response, self.message, success)
            
            # Log stats periodically
            stats = aura_bridge.get_stats()
            logging.info(f"AURA v2 Stats: Local={stats['local_commands']}, Saved={stats['tokens_saved']} tokens")
            
        except Exception as e:
            logging.error(f"Processing error: {e}")
            self.finished.emit(str(e), self.message, False)
"""
