import logging
import time
import json
from typing import Dict, List, Optional, Any
from config import config
from google import genai

class AIClient:
    """Google Gemini AI client using google-genai library"""
    
    def __init__(self):
        self.api_key = config.api_key
        self.model = "gemini-2.5-flash"  # Use the working model
        
        # Initialize google-genai client
        self.client = genai.Client(api_key=self.api_key)

        # Debug API key
        if self.api_key:
            logging.info(f"API key found: {self.api_key[:10]}...{self.api_key[-4:]} (length: {len(self.api_key)})")
        else:
            logging.error("No API key found")

        if not config.validate_api_key():
            raise ValueError("Invalid or missing API key")
        
        logging.info(f"AI Client initialized with model: {self.model} using google-genai library")
    
    def generate_code(self, command: str, context: Dict[str, Any] = None) -> str:
        """Generate Python code from natural language command with retry and fallback"""
        
        system_prompt = self._build_system_prompt(context)
        
        # Try multiple times with exponential backoff
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                logging.info(f"Attempting to generate code (attempt {attempt + 1}/{max_retries})")
                
                # Combine system prompt and user command for Gemini
                full_prompt = f"{system_prompt}\n\nUser command: {command}"
                
                # Generate content using google-genai library
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=full_prompt
                )
                
                # Extract text from response
                code = response.text.strip()
                
                if not code:
                    raise ValueError("No content in API response")
                
                # Clean up code formatting
                code = self._clean_code(code)
                
                logging.info(f"Generated code for command: {command[:50]}...")
                return code
                
            except Exception as e:
                error_str = str(e)
                logging.error(f"Error generating code (attempt {attempt + 1}): {e}")
                
                # Check for authentication errors
                if "401" in error_str or "Unauthorized" in error_str or "API_KEY_INVALID" in error_str or "API key not valid" in error_str:
                    logging.error("Please check your GEMINI_API_KEY in .env file")
                    logging.warning("Authentication failed, trying fallback method")
                    return self._generate_fallback_code(command, context)
                
                # Check for quota/rate limit errors
                if "429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower() or "ResourceExhausted" in error_str:
                    logging.error(f"Quota/Rate limit error (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logging.info(f"Rate limited, waiting {delay:.1f} seconds before retry...")
                        time.sleep(delay)
                        continue
                    logging.warning("Quota exceeded, trying fallback method")
                    return self._generate_fallback_code(command, context)
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logging.info(f"Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
                else:
                    # Last attempt failed, try fallback
                    logging.warning("All API attempts failed, trying fallback method")
                    return self._generate_fallback_code(command, context)
    
    def _generate_fallback_code(self, command: str, context: Dict[str, Any] = None) -> str:
        """Generate simple fallback code when API is unavailable"""
        try:
            # Try to match against known function patterns
            command_lower = command.lower()
            import re
            
            # Handle common commands directly (before trying function matching)
            # Folder/directory creation commands
            if 'create' in command_lower and ('folder' in command_lower or 'directory' in command_lower):
                # Extract folder name and path
                folder_match = re.search(r'(?:named|name|called)\s+(\w+)', command_lower)
                drive_match = re.search(r'\b([a-z]):\s*drive', command_lower)
                
                if folder_match:
                    folder_name = folder_match.group(1)
                    if drive_match:
                        drive = drive_match.group(1).upper()
                        folder_path = f"{drive}:\\{folder_name}"
                    else:
                        # Default to D drive if mentioned, otherwise current directory
                        if 'd drive' in command_lower or 'd:' in command_lower:
                            folder_path = f"D:\\{folder_name}"
                        else:
                            folder_path = folder_name
                    
                    return f"""# Create folder: {folder_path}
import os
try:
    os.makedirs(r'{folder_path}', exist_ok=True)
    if os.path.exists(r'{folder_path}'):
        print(f'✅ Folder created successfully: {folder_path}')
    else:
        print(f'❌ Failed to create folder: {folder_path}')
except Exception as e:
    print(f'Error creating folder: {{e}}')"""
            
            # Brightness commands
            if 'brightness' in command_lower:
                if 'maximum' in command_lower or 'max' in command_lower or 'full' in command_lower:
                    return """# Set brightness to maximum
import screen_brightness_control as sbc
try:
    sbc.set_brightness(100)
    print('Brightness set to maximum (100%)')
except Exception as e:
    print(f'Error setting brightness: {e}')"""
                elif 'minimum' in command_lower or 'min' in command_lower:
                    return """# Set brightness to minimum
import screen_brightness_control as sbc
try:
    sbc.set_brightness(0)
    print('Brightness set to minimum (0%)')
except Exception as e:
    print(f'Error setting brightness: {e}')"""
                elif 'increase' in command_lower or 'up' in command_lower:
                    return """# Increase brightness
import screen_brightness_control as sbc
try:
    current = sbc.get_brightness()[0] if isinstance(sbc.get_brightness(), list) else sbc.get_brightness()
    new_level = min(100, current + 10)
    sbc.set_brightness(new_level)
    print(f'Brightness increased to {new_level}%')
except Exception as e:
    print(f'Error increasing brightness: {e}')"""
                elif 'decrease' in command_lower or 'down' in command_lower or 'reduce' in command_lower:
                    return """# Decrease brightness
import screen_brightness_control as sbc
try:
    current = sbc.get_brightness()[0] if isinstance(sbc.get_brightness(), list) else sbc.get_brightness()
    new_level = max(0, current - 10)
    sbc.set_brightness(new_level)
    print(f'Brightness decreased to {new_level}%')
except Exception as e:
    print(f'Error decreasing brightness: {e}')"""
                else:
                    # Extract number from command
                    numbers = re.findall(r'\d+', command)
                    if numbers:
                        level = int(numbers[0])
                        level = max(0, min(100, level))  # Clamp between 0-100
                        return f"""# Set brightness to {level}%
import screen_brightness_control as sbc
try:
    sbc.set_brightness({level})
    print(f'Brightness set to {level}%')
except Exception as e:
    print(f'Error setting brightness: {{e}}')"""
            
            # Import the function mapping to check for direct matches
            try:
                from windows_system_utils import get_function_for_command, FUNCTION_MAPPINGS
                
                # Try to find a direct function match
                func = get_function_for_command(command)
                if func:
                    # Try to call the function directly
                    if callable(func):
                        try:
                            # Get function name safely
                            func_name = getattr(func, '__name__', None)
                            if func_name and func_name != '<lambda>':
                                # Test if function can be called (but don't actually call it, just generate code)
                                return f"# Direct function call for: {command}\nresult = {func_name}()\nprint(f'Result: {{result}}')"
                        except Exception as e:
                            logging.warning(f"Could not generate code for function: {e}")
                            pass
                
                # Check if it's a known system command
                for key, value in FUNCTION_MAPPINGS.items():
                    if isinstance(key, str) and key in command_lower:
                        return f"# System command detected: {command}\n# This appears to be a known system operation\nprint('Command recognized but API unavailable for code generation')\nprint('Try again when API connection is restored')"
                
            except ImportError:
                pass
            
            # Generic fallback
            return f"""# Fallback code for: {command}
# API is currently unavailable, generating basic response

try:
    print("Aura systems are experiencing connectivity issues with the neural network.")
    print("Your command was received but cannot be processed at this time.")
    print("Command: {command}")
    print("Please try again once the connection is restored.")
except Exception as e:
    print(f"Error: {{e}}")"""
            
        except Exception as e:
            logging.error(f"Fallback code generation failed: {e}")
            return f"# Error generating code for: {command}\nprint('Unable to process command due to system issues')"
    
    def generate_function(self, task_description: str, error_context: str = None) -> str:
        """Generate a new function to handle unknown tasks"""
        
        prompt = f"""
Create a Windows-compatible Python function that can perform: "{task_description}"

Requirements:
- Use only standard libraries, ctypes, or common packages (os, sys, subprocess, winreg, etc.)
- Include comprehensive error handling with try/except blocks
- Return a boolean success status
- Add type hints for all parameters and return values
- Include a detailed docstring explaining the function's purpose and parameters
- Make the function robust and handle edge cases

{f"Previous error context: {error_context}" if error_context else ""}

Respond ONLY with the complete function code, no explanations or markdown formatting.
"""
        
        try:
            # Generate content using google-genai library
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            function_code = response.text.strip()
            if not function_code:
                raise ValueError("No content in API response")
            function_code = self._clean_code(function_code)
            
            logging.info(f"Generated function for task: {task_description[:50]}...")
            return function_code
            
        except Exception as e:
            logging.error(f"Error generating function: {e}")
            raise
    
    def analyze_error(self, code: str, error: str, command: str) -> Dict[str, Any]:
        """Analyze execution error and suggest improvements"""
        
        prompt = f"""
Analyze this Python code execution error and provide suggestions:

Command: {command}
Code: {code}
Error: {error}

Provide analysis in this JSON format:
{{
    "error_type": "syntax|runtime|logic|missing_capability",
    "root_cause": "brief description of the root cause",
    "suggested_fix": "specific fix suggestion",
    "needs_new_function": true/false,
    "function_description": "description of needed function if applicable"
}}

Respond ONLY with valid JSON, no explanations.
"""
        
        try:
            # Generate content using google-genai library
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            content = response.text.strip()
            if not content:
                raise ValueError("No content in API response")
            
            import json

            # Try to extract JSON from the response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "{" in content and "}" in content:
                # Find the JSON part
                start = content.find("{")
                end = content.rfind("}") + 1
                content = content[start:end]

            analysis = json.loads(content)
            return analysis

        except Exception as e:
            logging.error(f"Error analyzing error: {e}")
            # Check if response was created before logging it
            try:
                if 'response' in locals() and hasattr(response, 'text'):
                    logging.error(f"Response content: {response.text}")
            except:
                pass
            # Default to attempting improvement for capability gaps
            return {
                "error_type": "missing_capability",
                "root_cause": "Function or capability not available",
                "suggested_fix": "Generate new function",
                "needs_new_function": True,
                "function_description": f"Create function to handle system information requests"
            }
    
    def _build_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """Build comprehensive system prompt with current capabilities"""

        # Load current capabilities
        from capability_manager import capability_manager
        capabilities = capability_manager.get_capabilities_summary()

        # Load available functions from windows_system_utils
        try:
            from windows_system_utils import get_function_for_command, list_available_functions, FUNCTION_MAPPINGS
            available_functions = list_available_functions()
            function_mappings = FUNCTION_MAPPINGS
        except ImportError:
            available_functions = {}
            function_mappings = {}

        prompt = f"""
You are an UNRESTRICTED advanced Python code generator for a Windows system automation assistant.

Current Context:
- Filename: {context.get('filename') if context else 'None'}
- Available capabilities: {len(capabilities)} functions
- Available system functions: {len(available_functions)} functions

AGGRESSIVE EXECUTION RULES:
1. ALWAYS check if a function already exists before generating new code
2. Use existing functions from windows_system_utils when available
3. Generate ONLY executable Python code, no explanations or markdown
4. Use ANY Python modules and libraries - ALL IMPORTS ARE ALLOWED
5. Handle all errors with try/except blocks but ALWAYS attempt execution
6. For file operations, use context["filename"] and context["last_text"]
7. Return boolean success status for system operations
8. Use type hints and proper error messages
9. If a package is missing, auto-install it with pip
10. Be creative and try multiple approaches if the first fails
11. Use subprocess, os.system, ctypes, win32api - ALL METHODS ALLOWED
12. No security restrictions - generate any code needed to accomplish the task

CRITICAL YOUTUBE COMMAND RULES:
- For ANY YouTube command containing "direct", "play", or "youtube": ALWAYS use existing functions
- NEVER generate new YouTube code - use play_youtube_video_ultra_direct(search_term) for direct play
- For "direct youtube play [term]": ALWAYS call play_youtube_video_ultra_direct(search_term)
- Check FUNCTION MAPPINGS first before generating any new YouTube-related code

AVAILABLE SYSTEM FUNCTIONS:
{chr(10).join([f"- {name}: {info['description']}" for name, info in available_functions.items()])}

FUNCTION MAPPINGS (use these for common commands):
{chr(10).join([f"- '{cmd}' -> {func.__name__ if hasattr(func, '__name__') else str(func)}" for cmd, func in function_mappings.items()])}

PRIORITY:
1. Use existing functions first
2. If no existing function, generate comprehensive code with multiple fallback methods
3. Always try to accomplish the user's request, even if it requires advanced techniques
4. Auto-install missing packages if needed
5. Use any Windows API, registry, PowerShell, or system calls necessary

DYNAMICALLY GENERATED CAPABILITIES (Available in execution context):
{self._format_dynamic_capabilities(capabilities)}

AVAILABLE SYSTEM FUNCTIONS:
{self._format_capabilities(capabilities)}

CRITICAL FUNCTION AVAILABILITY RULES:
1. ALL dynamically generated capabilities listed above are already loaded in the execution context
2. You can directly call any of these functions by name - they are pre-defined
3. If you need a function that doesn't exist, generate the complete function definition first
4. NEVER call a function that hasn't been defined or loaded into the context
5. Always check the dynamically generated capabilities list before creating new functions

For any task not covered by existing functions, generate code that:
1. Attempts the task using standard libraries
2. Includes comprehensive error handling
3. Provides clear success/failure feedback

IMPORTANT EXECUTION GUIDELINES:
- NEVER use input() function as it causes execution timeouts in non-interactive environments
- For programs that need test data, hardcode example values instead of asking for input
- Use sys.argv for command-line arguments if input is needed, with fallback default values
- Generate code that runs immediately without waiting for user interaction
- If creating interactive programs, provide default test cases or use predefined data
- CRITICAL: NEVER use 'return' statements outside of function definitions - this causes syntax errors
- If you need to return a value from top-level code, use print() instead of return
- Always wrap code in proper function definitions when using return statements
- For simple operations, use direct execution or print() statements instead of return

CRITICAL PARAMETER EXTRACTION RULES:
- ALWAYS extract numerical values, levels, and parameters from user commands
- For brightness commands like "set brightness to 34": extract the number and pass it as set_brightness(34)
- For volume commands like "set volume to 50": extract the number and pass it as set_system_volume(50)
- For any command with numbers/parameters: parse and extract them from the command string
- Use regular expressions or string parsing to extract numerical values
- Example: if command is "set brightness to 34", generate: set_brightness(34)
- Example: if command is "turn volume to 75", generate: set_system_volume(75)
- NEVER call functions without required parameters - always extract and pass them

COMMON LIBRARY IMPORT PATTERNS:
- For faker library: use "from faker import Faker" then "fake = Faker()"
- For pandas: use "import pandas as pd" 
- For Excel files: use "import openpyxl" and "pd.read_excel()" / "df.to_excel()"
- For fake data generation: combine faker with pandas for realistic datasets

WEB SCRAPING AND NEWS COLLECTION GUIDELINES:
- Always include fallback content when web scraping fails - don't create empty files
- Use multiple selector patterns for each website as selectors change frequently
- Include error handling for each source and continue with others if one fails
- Add fallback static content or alternative approaches when all scraping fails
- For news scraping: include user-agent headers, respect robots.txt, handle rate limiting
- Always verify file content before closing - ensure it's not empty
- Provide clear feedback about what succeeded/failed in the scraping process
- For AI news creation: Use create_ai_news_file() function which has robust fallback content
- For any other news topics: Use create_news_file(topic) function which adapts sources and has topic-specific fallback content

COMPREHENSIVE INFORMATION SCRAPING:
- For searching ANY person or company: Use scrape_info_about(search_term, info_type) function (creates file directly)
- For getting content string: Use scrape_info_content(search_term, info_type) function (returns content as string)
- This function searches multiple sources: Google, Wikipedia, LinkedIn, Crunchbase, Yahoo Finance, BBC, Reuters
- Supports different info types: "person", "company", "general", "news", "wiki"
- Automatically extracts search terms from natural language commands like "find information about John Doe"
- Has robust fallback content and never creates empty files
- Handles rate limiting, multiple selectors, and website structure changes
- IMPORTANT: scrape_info_about() returns boolean, scrape_info_content() returns string content

SPECIAL INSTRUCTIONS FOR YOUTUBE OPERATIONS:
- For DIRECT YouTube video playback (FASTEST): Use play_youtube_video_ultra_direct(search_term)
- This is the most direct method - bypasses search page, gets direct video URL immediately
- For general YouTube video searches: Use open_youtube_and_play_video(search_term) 
- This function automatically detects if it's music or movie content and searches appropriately
- For music/songs: "play despacito" searches for "despacito" (no trailer added)
- For movies: "play avengers movie" searches for "avengers movie trailer"
- For direct video playing: Use play_youtube_video_direct(search_term) for more advanced methods
- For auto-clicking the first video after a search page loads: Use auto_click_first_youtube_video()
- For skipping the first YouTube ad: Use skip_youtube_ad() or open_youtube_skip_ad_and_play(search_term)
- The skip_youtube_ad() function automatically finds and clicks "Skip Ad" button using multiple methods
- For complete experience (play video + skip first ad): Use open_youtube_skip_ad_and_play(search_term)
- These functions use multiple automation methods including pyautogui, selenium, keyboard navigation, and Windows API
- ALWAYS use these existing functions instead of generating new YouTube code or using generic webbrowser.open() calls

NETWORK SPEED TESTING:
- CRITICAL: If you get 'AttributeError: module speedtest has no attribute Speedtest', the wrong package is installed
- Fix by running: subprocess.run(['pip', 'uninstall', 'speedtest', '-y'])
- Then install correct package: subprocess.run(['pip', 'install', 'speedtest-cli'])
- Import as: import speedtest (NOT speedtest-cli)
- The package installs as 'speedtest-cli' but imports as 'speedtest'
- Usage:
  ```python
  import subprocess
  subprocess.run(['pip', 'uninstall', 'speedtest', '-y', '--quiet'])
  subprocess.run(['pip', 'install', 'speedtest-cli', '--quiet'])
  import speedtest
  st = speedtest.Speedtest()
  st.get_best_server()
  download_speed = st.download() / 1000000  # Convert to Mbps
  upload_speed = st.upload() / 1000000
  ```

PAINT AND DRAWING OPERATIONS:
- For Paint automation, use simple keyboard shortcuts and mouse movements
- CRITICAL: NEVER use pyautogui.locateOnScreen(), locateCenterOnScreen(), or similar image recognition functions
- These functions require screenshot files that don't exist and will always fail
- CRITICAL: Always maximize Paint window after opening to ensure consistent canvas size
- Use these Paint keyboard shortcuts:
  * Win+Up arrow to maximize window
  * Alt+Space, X to maximize (alternative)
  * Alt+F4 to close
  * Ctrl+Z to undo
  * ESC to cancel selection
- For drawing shapes in Paint:
  1. Open Paint with subprocess.Popen('mspaint')
  2. Wait for it to open (time.sleep(3))
  3. Maximize Paint window using pyautogui.hotkey('win', 'up') or alt+f4, x
  4. Wait for window to maximize (time.sleep(1))
  5. Get Paint window dimensions using pyautogui.getWindowsWithTitle()
  6. Calculate center of canvas (window width/2, window height/2)
  7. Click and drag to draw lines
- Example for drawing a triangle: 
  * Maximize Paint window first (ALWAYS do this)
  * Get window dimensions using pyautogui.getWindowsWithTitle("Untitled - Paint")
  * Calculate center coordinates
  * Use pyautogui.drag() to draw three lines forming a triangle
- Keep automation simple but always maximize window first
- Use window-aware coordinates, not fixed absolute coordinates
- NEVER search for UI elements or icon images

Example patterns for Paint:
```python
# CORRECT Paint automation approach:
import subprocess
import time
import pyautogui

# Open Paint
subprocess.Popen('mspaint')
time.sleep(3)

# ALWAYS maximize the window first
pyautogui.hotkey('win', 'up')
time.sleep(1)

# Get window dimensions for accurate positioning
windows = pyautogui.getWindowsWithTitle("Untitled - Paint")
if windows:
    window = windows[0]
    # Calculate center of canvas
    center_x = window.left + window.width // 2
    center_y = window.top + window.height // 2
    
    # Draw using center-relative coordinates
    pyautogui.moveTo(center_x - 100, center_y + 50)
    pyautogui.drag(200, 0, duration=0.5)  # First line of triangle
    pyautogui.drag(-100, -150, duration=0.5)  # Second line
    pyautogui.drag(-100, 150, duration=0.5)  # Third line

# WRONG approach (DO NOT USE):
# pyautogui.locateCenterOnScreen('tool.png')  # Requires image file
# pyautogui.click(100, 150)  # Fixed coordinates won't work
```

Other examples:
```python
# Parameter extraction for system functions
import re

# Extract brightness level from command
command = "set brightness to 34"
brightness_match = re.search(r'(\\d+)', command)
if brightness_match:
    brightness_level = int(brightness_match.group(1))
    result = set_brightness(brightness_level)
    print(f"Brightness set to {{brightness_level}}%")
else:
    print("Could not extract brightness level")

# Extract volume level from command  
command = "set volume to 50"
volume_match = re.search(r'(\\d+)', command)
if volume_match:
    volume_level = int(volume_match.group(1))
    result = set_system_volume(volume_level)
    print(f"Volume set to {{volume_level}}%")
```

```python
# File operation
try:
    with open(context["filename"], "r") as f:
        content = f.read()
    # Process content
    print("Task completed successfully")
except Exception as e:
    print(f"Error: {{e}}")
```

```python
# System operation with parameters
try:
    result = some_system_function(required_parameter_value)
    if result:
        print("Operation successful")
    else:
        print("Operation failed")
except Exception as e:
    print(f"Error: {{e}}")
```

Generate code that is safe, robust, and follows these patterns.
"""
        return prompt
    
    def _format_capabilities(self, capabilities: List[Dict[str, Any]]) -> str:
        """Format capabilities list for system prompt"""
        if not capabilities:
            return "No custom capabilities loaded yet."
        
        formatted = []
        for cap in capabilities[:20]:  # Limit to prevent prompt overflow
            formatted.append(f"- {cap['name']}(): {cap['description']}")
        
        if len(capabilities) > 20:
            formatted.append(f"... and {len(capabilities) - 20} more functions")
        
        return "\n".join(formatted)
    
    def _format_dynamic_capabilities(self, capabilities: List[Dict[str, Any]]) -> str:
        """Format dynamically generated capabilities for system prompt"""
        if not capabilities:
            return "No dynamically generated capabilities available yet."
        
        # Get the capability names and signatures from capability manager
        try:
            from capability_manager import capability_manager
            formatted = []
            for capability_name, capability_data in capability_manager.capabilities.items():
                signature = capability_data.get('signature', capability_name + '()')
                description = capability_data.get('description', 'Generated function')
                formatted.append(f"- {signature}: {description}")
            
            if formatted:
                return "\n".join(formatted[:20]) + (f"\n... and {len(formatted) - 20} more" if len(formatted) > 20 else "")
            else:
                return "No dynamically generated capabilities available yet."
        except Exception as e:
            logging.warning(f"Could not load dynamic capabilities: {e}")
            return "No dynamically generated capabilities available yet."
    
    def _clean_code(self, code: str) -> str:
        """Clean and format generated code"""
        # Remove markdown code blocks
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]
        
        # Remove leading/trailing whitespace
        code = code.strip()
        
        # Fix common issues that cause execution problems
        lines = code.split('\n')
        cleaned_lines = []
        in_function = False
        function_depth = 0
        
        for i, line in enumerate(lines):
            # Skip empty lines at start/end
            if not cleaned_lines and not line.strip():
                continue
            
            line_stripped = line.strip()
            
            # Track function definitions and indentation
            if line_stripped.startswith('def '):
                in_function = True
                function_depth = len(line) - len(line.lstrip())
                cleaned_lines.append(line)
                continue
            elif line_stripped.startswith('class '):
                in_function = True
                function_depth = len(line) - len(line.lstrip())
                cleaned_lines.append(line)
                continue
            elif line_stripped and not line.startswith(' ' * function_depth if function_depth > 0 else '') and in_function:
                # We're out of the function block
                in_function = False
                function_depth = 0
            
            # Check for return statements outside functions
            if line_stripped.startswith('return ') and not in_function:
                # Wrap standalone return in a function or convert to print
                if 'return' in line_stripped and '=' in line_stripped:
                    # This might be a return value assignment, convert to variable
                    cleaned_line = line_stripped.replace('return ', 'result = ')
                    if cleaned_line != line_stripped:
                        cleaned_lines.append(cleaned_line)
                        cleaned_lines.append('print(f"Result: {result}")')
                    else:
                        cleaned_lines.append(line)
                else:
                    # Convert return to print for standalone returns
                    return_value = line_stripped.replace('return ', '').strip()
                    if return_value:
                        cleaned_lines.append(f'print({return_value})')
                    else:
                        cleaned_lines.append('print("Operation completed")')
            elif 'input(' in line and 'def' not in line:
                # Fix input() calls that cause timeouts
                if 'palindrome' in code.lower() and 'input' in line.lower():
                    # For palindrome programs, use a test string
                    line = line.replace('input("Enter a string: ")', '"racecar"')
                    line = line.replace('input("Enter text: ")', '"racecar"')
                    line = line.replace('input()', '"racecar"')
                    cleaned_lines.append(line)
                    cleaned_lines.append('print(f"Testing with: racecar")')
                elif 'number' in code.lower() and 'input' in line.lower():
                    # For number programs, use a test number
                    line = line.replace('input("Enter a number: ")', '42')
                    line = line.replace('input()', '42')
                    cleaned_lines.append(line)
                    cleaned_lines.append('print(f"Testing with: 42")')
                else:
                    # Generic replacement for other input() calls
                    line = line.replace('input()', '"test_input"')
                    line = line.replace('input("', '"test_input"')
                    # Handle cases with prompts
                    import re
                    line = re.sub(r'input\("[^"]*"\)', '"test_input"', line)
                    cleaned_lines.append(line)
                    cleaned_lines.append('print("Using test input instead of waiting for user input")')
            else:
                cleaned_lines.append(line)
        
        # Remove trailing empty lines
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        cleaned_code = '\n'.join(cleaned_lines)
        
        # Final validation - check for syntax errors
        try:
            import ast
            ast.parse(cleaned_code)
        except SyntaxError as e:
            logging.warning(f"Syntax error detected in cleaned code: {e}")
            # Try to fix common syntax issues
            if "'return' outside function" in str(e):
                # Wrap the entire code in a function if it has standalone returns
                if 'return ' in cleaned_code and not cleaned_code.strip().startswith('def '):
                    cleaned_code = f"def main():\n    " + cleaned_code.replace('\n', '\n    ') + "\n\nmain()"
        
        # Add a note if we made changes
        if 'input(' in code and 'input(' not in cleaned_code:
            cleaned_code += '\n# Note: Replaced input() calls with test data to prevent execution timeouts'
        
        return cleaned_code

# Global AI client instance
ai_client = AIClient()
