#!/usr/bin/env python3
"""
Advanced Self-Improving AI Assistant
A secure, modular AI assistant that learns and adapts to new tasks
"""

import logging
import sys
import os
from typing import Dict, Any, Optional
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from ai_client import ai_client
from code_executor import executor
from capability_manager import capability_manager
from self_improvement import improvement_engine
from voice_interface import VoiceInterface, TextInterface

class AIAssistant:
    """Main AI Assistant class that coordinates all components"""
    
    def __init__(self):
        self.context = {
            "filename": None,
            "last_text": "",
            "session_start": None,
            "command_count": 0
        }
        
        self.voice_interface = None
        self.text_interface = None
        self.current_interface = None
        
        # Initialize interfaces
        self._initialize_interfaces()
        
        logging.info("AI Assistant initialized successfully")
    
    def _initialize_interfaces(self):
        """Initialize voice and text interfaces"""
        try:
            if config.get('voice.enabled', True):
                self.voice_interface = VoiceInterface()
                logging.info("Voice interface initialized")
        except Exception as e:
            logging.warning(f"Voice interface initialization failed: {e}")
        
        self.text_interface = TextInterface()
        logging.info("Text interface initialized")
    
    def start(self):
        """Start the assistant and main interaction loop"""
        print("🤖 Advanced AI Assistant Starting...")
        print("=" * 50)
        
        # Display system status
        self._display_status()
        
        # Choose interface
        interface_choice = self._choose_interface()
        
        if interface_choice == "voice" and self.voice_interface:
            self.current_interface = self.voice_interface
            print("🎤 Voice mode activated. Say 'exit' or 'quit' to stop.")
        else:
            self.current_interface = self.text_interface
            print("⌨️  Text mode activated. Type 'exit' or 'quit' to stop.")
        
        # Main interaction loop
        self._main_loop()
    
    def _display_status(self):
        """Display current system status"""
        capabilities_count = len(capability_manager.capabilities)
        improvement_stats = improvement_engine.get_improvement_stats()
        
        print(f"📊 System Status:")
        print(f"   • Available capabilities: {capabilities_count}")
        print(f"   • Improvement attempts: {improvement_stats['total_attempts']}")
        print(f"   • Successful improvements: {improvement_stats['successful_improvements']}")
        print(f"   • Learning enabled: {config.get('learning.auto_improve', True)}")
        print()
    
    def _choose_interface(self) -> str:
        """Let user choose between voice and text interface"""
        if not self.voice_interface:
            return "text"
        
        while True:
            choice = input("Choose interface (voice/text): ").strip().lower()
            if choice in ["voice", "text"]:
                return choice
            print("Please enter 'voice' or 'text'")
    
    def _main_loop(self):
        """Main interaction loop"""
        from datetime import datetime
        self.context["session_start"] = datetime.now().isoformat()
        
        try:
            while True:
                # Get command from user
                command = self.current_interface.get_input()
                
                if not command:
                    continue
                
                # Check for exit commands
                if any(word in command.lower() for word in ["exit", "quit", "goodbye", "stop"]):
                    self._handle_exit()
                    break
                
                # Check for special commands
                if self._handle_special_commands(command):
                    continue
                
                # Process the command
                self._process_command(command)
                
        except KeyboardInterrupt:
            print("\n👋 Assistant stopped by user")
        except Exception as e:
            logging.error(f"Unexpected error in main loop: {e}")
            print(f"❌ Unexpected error: {e}")
        finally:
            self._cleanup()
    
    def _handle_special_commands(self, command: str) -> bool:
        """Handle special system commands"""
        command_lower = command.lower().strip()
        
        if command_lower == "status":
            self._display_detailed_status()
            return True
        
        elif command_lower == "capabilities":
            self._display_capabilities()
            return True
        
        elif command_lower == "learning":
            self._display_learning_info()
            return True
        
        elif command_lower.startswith("switch to "):
            interface_type = command_lower.replace("switch to ", "").strip()
            return self._switch_interface(interface_type)
        
        elif command_lower == "help":
            self._display_help()
            return True
        
        return False
    
    def _process_command(self, command: str):
        """Process a user command"""
        self.context["command_count"] += 1
        
        try:
            # Inform user we're processing
            self.current_interface.output("🤔 Processing your request...")
            
            # Generate code for the command
            code = ai_client.generate_code(command, self.context)
            
            if not code:
                self.current_interface.output("❌ Could not generate code for this command")
                return
            
            print(f"\n📝 Generated Code:\n{code}\n")
            
            # Execute the code
            success, output, result = executor.execute(code, self._get_execution_context())
            
            if success:
                self.current_interface.output("✅ Task completed successfully!")
                if output:
                    print(f"Output: {output}")
                
                # Record success
                capability_manager.record_execution(command, True)
                
            else:
                self.current_interface.output("❌ Execution failed")
                print(f"Error: {output}")
                
                # Attempt self-improvement
                improved, improvement_msg, execution_output = improvement_engine.handle_execution_failure(command, code, output)
                
                if improved:
                    self.current_interface.output(f"🎯 {improvement_msg}")
                    if execution_output and execution_output.strip():
                        self.current_interface.output(f"✅ Task completed successfully!\nOutput: {execution_output}")
                    else:
                        # Retry the command if no execution output
                        self.current_interface.output("🔄 Retrying with new capability...")
                        self._process_command(command)
                else:
                    self.current_interface.output(f"ℹ️  {improvement_msg}")
                
        except Exception as e:
            logging.error(f"Error processing command '{command}': {e}")
            self.current_interface.output(f"❌ Error processing command: {e}")
    
    def _get_execution_context(self) -> Dict[str, Any]:
        """Get context for code execution"""
        # Import all available system functions
        context = {
            'context': self.context,
            'print': print,
            'input': input,
        }
        
        # Import system utilities
        try:
            import windows_system_utils
            for attr_name in dir(windows_system_utils):
                if not attr_name.startswith('_'):
                    context[attr_name] = getattr(windows_system_utils, attr_name)
        except Exception as e:
            logging.warning(f"Could not import system utilities: {e}")
        
        # Load dynamically generated capabilities
        try:
            self._load_generated_capabilities_into_context(context)
        except Exception as e:
            logging.warning(f"Could not load generated capabilities: {e}")
        
        return context
    
    def _load_generated_capabilities_into_context(self, context: Dict[str, Any]):
        """Load generated capabilities into execution context"""
        try:
            # Get all capabilities from capability manager
            capabilities_count = len(capability_manager.capabilities)
            logging.info(f"Loading {capabilities_count} capabilities into execution context")
            
            for capability_name, capability_data in capability_manager.capabilities.items():
                try:
                    # Execute the function code to make it available in context
                    function_code = capability_data.get("code", "")
                    if function_code:
                        # Create a temporary execution environment to define the function
                        temp_context = context.copy()
                        # Add builtins to temp context for proper execution
                        import builtins
                        temp_context['__builtins__'] = builtins.__dict__.copy()
                        exec(function_code, temp_context)
                        
                        # Extract the function from the temporary context and add to main context
                        function_loaded = False
                        for name, value in temp_context.items():
                            if not name.startswith('_') and callable(value) and name == capability_name:
                                context[capability_name] = value
                                logging.info(f"Successfully loaded capability into context: {capability_name}")
                                function_loaded = True
                                break
                        
                        if not function_loaded:
                            logging.warning(f"Could not find function {capability_name} after execution")
                    else:
                        logging.warning(f"No function code found for capability: {capability_name}")
                except Exception as e:
                    logging.warning(f"Could not load capability {capability_name}: {e}")
                    
            logging.info(f"Finished loading capabilities. Context now has {len([k for k in context.keys() if not k.startswith('_')])} non-private items")
        except Exception as e:
            logging.error(f"Error loading generated capabilities: {e}")
    
    def _display_detailed_status(self):
        """Display detailed system status"""
        stats = improvement_engine.get_improvement_stats()
        capabilities = capability_manager.get_capabilities_summary()
        
        print("\n📊 Detailed System Status:")
        print(f"   Session commands: {self.context['command_count']}")
        print(f"   Total capabilities: {len(capabilities)}")
        print(f"   Improvement success rate: {stats['success_rate']:.1%}")
        print(f"   Active failure patterns: {stats['active_failure_patterns']}")
        print()
    
    def _display_capabilities(self):
        """Display available capabilities"""
        capabilities = capability_manager.get_capabilities_summary()
        
        if not capabilities:
            print("No custom capabilities learned yet.")
            return
        
        print(f"\n🛠️  Available Capabilities ({len(capabilities)}):")
        for cap in capabilities[:10]:  # Show first 10
            success_rate = cap.get('success_rate', 0)
            print(f"   • {cap['name']}: {cap['description']} (Success: {success_rate:.1%})")
        
        if len(capabilities) > 10:
            print(f"   ... and {len(capabilities) - 10} more")
        print()
    
    def _display_learning_info(self):
        """Display learning and improvement information"""
        suggestions = improvement_engine.suggest_learning_opportunities()
        
        print("\n🧠 Learning Information:")
        if suggestions:
            for suggestion in suggestions:
                print(f"   • {suggestion}")
        else:
            print("   • System is learning well - no specific suggestions")
        print()
    
    def _switch_interface(self, interface_type: str) -> bool:
        """Switch between voice and text interfaces"""
        if interface_type == "voice" and self.voice_interface:
            self.current_interface = self.voice_interface
            print("🎤 Switched to voice mode")
            return True
        elif interface_type == "text":
            self.current_interface = self.text_interface
            print("⌨️  Switched to text mode")
            return True
        else:
            print(f"❌ Cannot switch to {interface_type} interface")
            return True
    
    def _display_help(self):
        """Display help information"""
        print("\n❓ Help - Available Commands:")
        print("   • Any natural language command (e.g., 'open notepad', 'hide desktop icons')")
        print("   • status - Show system status")
        print("   • capabilities - List learned capabilities")
        print("   • learning - Show learning information")
        print("   • switch to voice/text - Change interface")
        print("   • help - Show this help")
        print("   • exit/quit - Stop the assistant")
        print()
    
    def _handle_exit(self):
        """Handle exit command"""
        stats = improvement_engine.get_improvement_stats()
        
        print(f"\n👋 Session Summary:")
        print(f"   Commands processed: {self.context['command_count']}")
        print(f"   Capabilities learned: {stats['successful_improvements']}")
        print(f"   Thank you for using the AI Assistant!")
    
    def _cleanup(self):
        """Cleanup resources"""
        if self.voice_interface:
            self.voice_interface.cleanup()

def main():
    """Main entry point"""
    try:
        # Validate configuration
        if not config.validate_api_key():
            print("❌ Please set your GEMINI_API_KEY environment variable")
            return 1
        
        # Start the assistant
        assistant = AIAssistant()
        assistant.start()
        
        return 0
        
    except Exception as e:
        logging.error(f"Failed to start assistant: {e}")
        print(f"❌ Failed to start assistant: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
