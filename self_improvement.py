import logging
import ast
import re
import subprocess
import sys
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from ai_client import ai_client
from capability_manager import capability_manager
from code_executor import executor
from config import config

class SelfImprovementEngine:
    """Advanced self-improvement system that learns and adapts"""

    def __init__(self):
        self.improvement_attempts = 0
        self.successful_improvements = 0
        self.learning_threshold = 1  # Reduced to 1 for faster learning
        self.recent_failures = {}  # Track recent failures by command pattern

        # Safe packages that can be auto-installed
        self.safe_packages = {
            'screen_brightness_control': 'screen-brightness-control',
            'psutil': 'psutil',
            'requests': 'requests',
            'pillow': 'Pillow',
            'opencv': 'opencv-python',
            'numpy': 'numpy',
            'pandas': 'pandas',
            'matplotlib': 'matplotlib',
            'selenium': 'selenium',
            'beautifulsoup4': 'beautifulsoup4',
            'lxml': 'lxml',
            'openpyxl': 'openpyxl',
            'pyautogui': 'pyautogui',
            'keyboard': 'keyboard',
            'mouse': 'mouse',
            'schedule': 'schedule',
            'colorama': 'colorama',
            'tqdm': 'tqdm',
            'click': 'click',
            'faker': 'faker',
            'speedtest': 'speedtest-cli',
            # Office and Document modules
            'pptx': 'python-pptx',
            'docx': 'python-docx',
            'xlsxwriter': 'xlsxwriter',
            'xlrd': 'xlrd',
            'xlwt': 'xlwt',
            # Image and Media processing
            'moviepy': 'moviepy',
            'imageio': 'imageio',
            'scikit_image': 'scikit-image',
            'plotly': 'plotly',
            'seaborn': 'seaborn',
            # Web and API
            'urllib3': 'urllib3',
            'httpx': 'httpx',
            'aiohttp': 'aiohttp',
            'websocket': 'websocket-client',
            # Database modules
            'pymongo': 'pymongo',
            'psycopg2': 'psycopg2-binary',
            'mysql': 'mysql-connector-python',
            # Audio and Speech
            'speech_recognition': 'SpeechRecognition',
            'pyttsx3': 'pyttsx3',
            'pyaudio': 'pyaudio',
            'pydub': 'pydub',
            'pyaudio-utils': 'pyaudio-utils',
            'pyaudio-devices': 'pyaudio-devices',
            'pyaudio-utils': 'pyaudio-utils',
            'pyaudio-devices': 'pyaudio-devices',
            'pycaw': 'pycaw',
            'comtypes': 'comtypes',
            'pywin32': 'pywin32',
            'wmi': 'wmi',
            # Network and Security
            'cryptography': 'cryptography',
            # Date and Time
            'dateutil': 'python-dateutil',
            'arrow': 'arrow',
            'caldav': 'caldav',
            # Scientific Computing
            'scipy': 'scipy',
            'sympy': 'sympy',
            'statsmodels': 'statsmodels',
            'sklearn': 'scikit-learn',
            # GUI and Desktop
            'pyqt5': 'PyQt5',
            'kivy': 'kivy',
            'wx': 'wxPython',
            # Cloud and Services
            'boto3': 'boto3',
            'azure': 'azure-storage-blob',
            'google': 'google-cloud-storage',
            'dropbox': 'dropbox',
            # Development Tools
            'black': 'black',
            'pytest': 'pytest',
            'flake8': 'flake8',
            'mypy': 'mypy',
            # Text Processing
            'nltk': 'nltk',
            'spacy': 'spacy',
            'textblob': 'textblob',
            'jieba': 'jieba',
            # Automation and Scripting
            'schedule': 'schedule',
            'apscheduler': 'apscheduler',
            'celery': 'celery',
            'rq': 'rq',
            # Email and Communication
            # COM/Automation (Windows)
            'comtypes': 'comtypes',
            'pywin32': 'pywin32',
            'wmi': 'wmi'
        }

        # Local modules that should be allowed (including built-in modules)
        self.safe_local_modules = {
            'windows_system_utils',
            'ai_client',
            'capability_manager',
            'code_executor',
            'config',
            'self_improvement',
            # Built-in modules that don't need installation
            'os', 'sys', 'json', 'csv', 'xml', 'html', 'sqlite3', 'shutil', 
            'pathlib', 'glob', 'zipfile', 'tarfile', 'gzip', 'hashlib',
            'base64', 'secrets', 'smtplib', 'email', 'imaplib', 'poplib',
            'ftplib', 'tkinter', 'urllib', 'http', 'socket', 'ssl', 'threading',
            'multiprocessing', 'subprocess', 'logging', 'datetime', 'time',
            'calendar', 'collections', 'itertools', 'functools', 'operator',
            'math', 'random', 'statistics', 'decimal', 'fractions'
        }

        logging.info("Self-Improvement Engine initialized")
    
    def handle_execution_failure(self, command: str, code: str, error: str) -> Tuple[bool, str, str]:
        """
        Handle execution failure and attempt self-improvement
        Returns: (improved, result_message, execution_output)
        """
        logging.info(f"Handling execution failure for command: {command[:50]}...")
        
        # Record the failure
        capability_manager.record_execution(command, False)
        
        # Check if we should attempt improvement
        if not capability_manager.should_attempt_improvement(command, error):
            return False, f"No improvement attempted: {error}", error
        
        # Track failure patterns
        command_pattern = self._extract_command_pattern(command)
        if command_pattern not in self.recent_failures:
            self.recent_failures[command_pattern] = []
        
        self.recent_failures[command_pattern].append({
            "command": command,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
        
        # Always attempt improvement immediately (threshold disabled)
        # if len(self.recent_failures[command_pattern]) < self.learning_threshold:
        #     return False, f"Tracking failure pattern ({len(self.recent_failures[command_pattern])}/{self.learning_threshold})"

        # Auto-install missing packages if needed
        if "no module named" in error.lower() or "cannot import" in error.lower():
            self._auto_install_missing_package(error)

        # Auto-fix common execution errors
        if "name" in error.lower() and "not defined" in error.lower():
            self._auto_fix_undefined_names(command, code, error)
        
        # Attempt improvement
        return self._attempt_improvement(command, code, error)
    
    def _extract_command_pattern(self, command: str) -> str:
        """Extract a pattern from the command for grouping similar failures"""
        # Remove specific details and keep general intent
        pattern = command.lower()
        
        # Remove specific file names, numbers, etc.
        pattern = re.sub(r'\b\d+\b', 'NUMBER', pattern)
        pattern = re.sub(r'\b[a-zA-Z]:\\[^\s]+', 'PATH', pattern)
        pattern = re.sub(r'\b\w+\.(txt|py|doc|pdf|jpg|png)\b', 'FILE', pattern)
        
        # Extract key action words
        action_words = ['open', 'close', 'create', 'delete', 'move', 'copy', 'run', 'start', 'stop', 
                       'show', 'hide', 'enable', 'disable', 'set', 'get', 'change', 'toggle']
        
        found_actions = [word for word in action_words if word in pattern]
        if found_actions:
            return f"{found_actions[0]}_action"
        
        return "general_command"

    def _detect_missing_modules(self, error: str) -> List[str]:
        """Detect missing modules from error messages"""
        missing_modules = []

        # Common import error patterns
        import_patterns = [
            r"No module named '([^']+)'",
            r"ModuleNotFoundError: No module named '([^']+)'",
            r"ImportError: No module named ([^\s]+)",
            r"cannot import name '([^']+)'",
            r"Forbidden import: ([^\s,]+)"
        ]

        for pattern in import_patterns:
            matches = re.findall(pattern, error)
            missing_modules.extend(matches)

        return list(set(missing_modules))  # Remove duplicates

    def _auto_install_package(self, module_name: str) -> bool:
        """Automatically install a safe package or allow local modules"""
        try:
            # Check if it's a local module that should be allowed
            if module_name in self.safe_local_modules:
                logging.info(f"✅ Local module '{module_name}' is safe - allowing import")
                print(f"✅ Local module '{module_name}' is safe - allowing import")
                return True

            # Check if it's in our safe packages list
            if module_name not in self.safe_packages:
                logging.warning(f"Module '{module_name}' not in safe packages list")
                return False

            package_name = self.safe_packages[module_name]

            logging.info(f"Auto-installing package: {package_name}")
            print(f"Auto-installing package: {package_name}...")

            # Install the package
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", package_name
            ], capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                logging.info(f"Successfully installed {package_name}")
                print(f"Successfully installed {package_name}")
                return True
            else:
                logging.error(f"Failed to install {package_name}: {result.stderr}")
                print(f"Failed to install {package_name}")
                return False

        except subprocess.TimeoutExpired:
            logging.error(f"Installation timeout for {package_name}")
            return False
        except Exception as e:
            logging.error(f"Installation error for {package_name}: {e}")
            return False

    def _auto_update_security_config(self, module_name: str) -> bool:
        """Automatically add module to security whitelist"""
        try:
            current_modules = config.get('security.allowed_modules', [])

            if module_name not in current_modules:
                current_modules.append(module_name)
                config.set('security.allowed_modules', current_modules)

                logging.info(f"Added {module_name} to security whitelist")
                print(f"Added {module_name} to security whitelist")
                return True
            else:
                logging.info(f"{module_name} already in security whitelist")
                return True

        except Exception as e:
            logging.error(f"Failed to update security config: {e}")
            return False
    
    def _attempt_improvement(self, command: str, failed_code: str, error: str) -> Tuple[bool, str, str]:
        """Attempt to improve capabilities with auto-installation"""
        self.improvement_attempts += 1

        try:
            # First, try to detect and auto-install missing modules
            missing_modules = self._detect_missing_modules(error)

            if missing_modules:
                logging.info(f"Detected missing modules: {missing_modules}")
                print(f"Detected missing modules: {missing_modules}")

                installed_any = False
                for module in missing_modules:
                    # Try auto-installation
                    if self._auto_install_package(module):
                        # Update security config
                        if self._auto_update_security_config(module):
                            installed_any = True

                if installed_any:
                    print("Retrying command with newly installed modules...")

                    # Generate new code with the now-available modules
                    try:
                        new_code = ai_client.generate_code(command)
                        execution_context = self._get_execution_context_with_capabilities()
                        exec_result = executor.execute(new_code, execution_context)
                        if exec_result[0]:
                            self.successful_improvements += 1
                            capability_manager.record_execution(command, True)

                            # Clear failure history
                            pattern = self._extract_command_pattern(command)
                            if pattern in self.recent_failures:
                                del self.recent_failures[pattern]

                            logging.info(f"Auto-improvement successful for: {command[:50]}...")
                            return True, "Auto-installed missing modules and regenerated code successfully!", exec_result[1]
                        else:
                            logging.info("Auto-installation completed but regenerated code still failed")
                            return False, f"Auto-installation completed but regenerated code still failed: {exec_result[1]}", exec_result[1]
                    except Exception as e:
                        logging.error(f"Error regenerating code after auto-install: {e}")
                        logging.info("Auto-installation completed but code regeneration failed")
                        return False, f"Auto-installation completed but code regeneration failed: {e}", str(e)

            # If auto-installation didn't work, try generating new functions
            analysis = ai_client.analyze_error(failed_code, error, command)

            if not analysis.get("needs_new_function", False):
                # Even if no new function needed, try regenerating the code with better approach
                logging.info("No new function needed, but attempting code regeneration with improved approach")
                try:
                    new_code = ai_client.generate_code(command)
                    execution_context = self._get_execution_context_with_capabilities()
                    exec_result = executor.execute(new_code, execution_context)
                    if exec_result[0]:
                        self.successful_improvements += 1
                        capability_manager.record_execution(command, True)
                        return True, "Code regenerated with improved approach and executed successfully!", exec_result[1]
                    else:
                        return False, f"Code regeneration still failed: {exec_result[1]}", exec_result[1]
                except Exception as e:
                    logging.error(f"Code regeneration error: {e}")
                    return False, f"Analysis suggests: {analysis.get('suggested_fix', 'Unknown fix')}. Code regeneration failed: {e}", error

            # Generate a new function to handle this capability
            function_description = analysis.get("function_description", command)
            new_function_code = ai_client.generate_function(function_description, error)

            # Validate the generated function
            if not self._validate_generated_function(new_function_code):
                return False, "Generated function failed validation", error

            # Test the function in isolation
            test_result = self._test_generated_function(new_function_code, command)
            if not test_result[0]:
                return False, f"Generated function failed testing: {test_result[1]}", error

            # Add the capability
            success = capability_manager.add_capability(new_function_code, command, True)
            if not success:
                return False, "Failed to add new capability", error

            # Generate new code using the new capability
            new_code = ai_client.generate_code(command)

            # Test the new code with proper execution context
            execution_context = self._get_execution_context_with_capabilities()
            exec_result = executor.execute(new_code, execution_context)
            if exec_result[0]:
                self.successful_improvements += 1
                capability_manager.record_execution(command, True)

                # Clear failure history for this pattern
                pattern = self._extract_command_pattern(command)
                if pattern in self.recent_failures:
                    del self.recent_failures[pattern]

                logging.info(f"Successfully improved capability for: {command[:50]}...")
                return True, f"Improvement successful! New capability added and tested.", exec_result[1]
            else:
                return False, f"New code still failed: {exec_result[1]}", exec_result[1]

        except Exception as e:
            logging.error(f"Error during improvement attempt: {e}")
            return False, f"Improvement failed due to error: {e}", str(e)
    
    def _validate_generated_function(self, function_code: str) -> bool:
        """Validate that generated function meets quality standards"""
        try:
            # Parse the code
            tree = ast.parse(function_code)
            func_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            
            if not func_nodes:
                logging.warning("No function definition found")
                return False
            
            func_node = func_nodes[0]
            
            # Check for required elements
            has_docstring = ast.get_docstring(func_node) is not None
            has_error_handling = self._has_error_handling(func_node)
            has_return_statement = self._has_return_statement(func_node)
            
            if not has_docstring:
                logging.warning("Generated function lacks docstring")
                return False
            
            if not has_error_handling:
                logging.warning("Generated function lacks error handling")
                return False
            
            if not has_return_statement:
                logging.warning("Generated function lacks return statement")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error validating function: {e}")
            return False
    
    def _has_error_handling(self, func_node: ast.FunctionDef) -> bool:
        """Check if function has try/except blocks"""
        for node in ast.walk(func_node):
            if isinstance(node, ast.Try):
                return True
        return False
    
    def _has_return_statement(self, func_node: ast.FunctionDef) -> bool:
        """Check if function has return statements"""
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return):
                return True
        return False
    
    def _test_generated_function(self, function_code: str, original_command: str) -> Tuple[bool, str]:
        """Test the generated function in a safe environment"""
        try:
            # Create a test context
            test_context = {
                'print': lambda *args: None,  # Suppress output during testing
                'logging': logging,
                'os': __import__('os'),
                'sys': __import__('sys'),
                'ctypes': __import__('ctypes'),
                'subprocess': __import__('subprocess'),
                'time': __import__('time'),
            }
            
            # Execute the function definition
            exec_result = executor.execute(function_code, test_context)
            
            if not exec_result[0]:
                return False, f"Function execution failed: {exec_result[1]}"
            
            # Try to extract and call the function with safe parameters
            tree = ast.parse(function_code)
            func_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            
            if func_nodes:
                func_name = func_nodes[0].name
                
                # Create a simple test call (this is basic - could be enhanced)
                test_call = f"result = {func_name}()"
                test_result = executor.execute(test_call, test_context)
                
                if test_result[0]:
                    return True, "Function test passed"
                else:
                    return False, f"Function test failed: {test_result[1]}"
            
            return True, "Function definition successful"
            
        except Exception as e:
            return False, f"Test error: {e}"

    def _auto_install_missing_package(self, error: str) -> bool:
        """Automatically install missing packages with correct package names"""
        try:
            import re
            import subprocess

            # Extract package name from error
            patterns = [
                r"No module named '([^']+)'",
                r"cannot import name '([^']+)'",
                r"ModuleNotFoundError: No module named '([^']+)'"
            ]

            package_name = None
            for pattern in patterns:
                match = re.search(pattern, error)
                if match:
                    package_name = match.group(1)
                    break

            if package_name:
                # Map common import names to correct package names
                package_mapping = {
                    'cv2': 'opencv-python',
                    'PIL': 'Pillow',
                    'sklearn': 'scikit-learn',
                    'yaml': 'PyYAML',
                    'bs4': 'beautifulsoup4',
                    'requests': 'requests',
                    'numpy': 'numpy',
                    'pandas': 'pandas',
                    'matplotlib': 'matplotlib',
                    'seaborn': 'seaborn',
                    'scipy': 'scipy',
                    'tensorflow': 'tensorflow',
                    'torch': 'torch',
                    'flask': 'Flask',
                    'django': 'Django',
                    'speedtest': 'speedtest-cli',
                    'fastapi': 'fastapi',
                    'psutil': 'psutil',
                    'pyautogui': 'pyautogui',
                    'keyboard': 'keyboard',
                    'mouse': 'mouse',
                    'win32api': 'pywin32',
                    'win32gui': 'pywin32',
                    'win32con': 'pywin32',
                    'pywintypes': 'pywin32',
                    'faker': 'faker',
                    'mss': 'mss',
                    'pygetwindow': 'pygetwindow',
                    'pygettext': 'pygettext',
                    'pygettext': 'pygettext',
                    'googleapiclient': 'google-api-python-client',
                    'google-api-python-client': 'google-api-python-client',
                    'google-api-core': 'google-api-core',
                    'google-auth': 'google-auth',
                    'google-auth-oauthlib': 'google-auth-oauthlib',
                    'google-auth-httplib2': 'google-auth-httplib2',
                    'google-auth-oauthlib': 'google-auth-oauthlib',
                }

                # Get the correct package name
                install_name = package_mapping.get(package_name, package_name)

                print(f"Auto-installing missing package: {package_name} -> {install_name}")
                result = subprocess.run([
                    "pip", "install", install_name
                ], capture_output=True, text=True)

                if result.returncode == 0:
                    print(f"Successfully installed {install_name}")
                    return True
                else:
                    print(f"Failed to install {install_name}: {result.stderr}")
                    return False

            return False

        except Exception as e:
            print(f"Error in auto-install: {e}")
            return False

    def _auto_fix_undefined_names(self, command: str, code: str, error: str) -> bool:
        """Automatically fix undefined name errors by adding imports"""
        try:
            import re

            # Extract undefined name from error
            match = re.search(r"name '([^']+)' is not defined", error)
            if not match:
                return False

            undefined_name = match.group(1)

            # Common imports for undefined names
            common_imports = {
                'os': 'import os',
                'sys': 'import sys',
                'time': 'import time',
                'datetime': 'from datetime import datetime',
                'subprocess': 'import subprocess',
                'json': 'import json',
                're': 'import re',
                'math': 'import math',
                'random': 'import random',
                'pathlib': 'from pathlib import Path',
                'typing': 'from typing import *',
                'ctypes': 'import ctypes',
                'winreg': 'import winreg',
                'platform': 'import platform'
            }

            if undefined_name in common_imports:
                print(f"🔧 Auto-fixing undefined name: {undefined_name}")
                # This would be handled by the code regeneration process
                return True

            return False

        except Exception as e:
            print(f"Error in auto-fix: {e}")
            return False

    def get_improvement_stats(self) -> Dict[str, Any]:
        """Get statistics about improvement attempts"""
        success_rate = 0.0
        if self.improvement_attempts > 0:
            success_rate = self.successful_improvements / self.improvement_attempts
        
        return {
            "total_attempts": self.improvement_attempts,
            "successful_improvements": self.successful_improvements,
            "success_rate": success_rate,
            "active_failure_patterns": len(self.recent_failures),
            "total_capabilities": len(capability_manager.capabilities)
        }
    
    def suggest_learning_opportunities(self) -> List[str]:
        """Suggest areas where the system could learn new capabilities"""
        suggestions = []
        
        # Analyze failure patterns
        for pattern, failures in self.recent_failures.items():
            if len(failures) >= self.learning_threshold:
                suggestions.append(f"Pattern '{pattern}' has {len(failures)} recent failures - consider manual capability addition")
        
        # Analyze successful commands for potential generalizations
        similar_commands = capability_manager.find_similar_commands("", limit=10)
        if len(similar_commands) < 5:
            suggestions.append("Limited command history - system will learn more as you use it")
        
        return suggestions
    
    def _get_execution_context_with_capabilities(self) -> Dict[str, Any]:
        """Get execution context that includes dynamically generated capabilities"""
        context = {
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
            capabilities_count = len(capability_manager.capabilities)
            logging.info(f"Self-improvement: Loading {capabilities_count} capabilities into execution context")
            
            # Get all capabilities from capability manager
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
                                logging.info(f"Self-improvement: Successfully loaded capability {capability_name}")
                                function_loaded = True
                                break
                        
                        if not function_loaded:
                            logging.warning(f"Self-improvement: Could not find function {capability_name} after execution")
                    else:
                        logging.warning(f"No function code found for capability: {capability_name}")
                except Exception as e:
                    logging.warning(f"Could not load capability {capability_name}: {e}")
        except Exception as e:
            logging.error(f"Error loading generated capabilities: {e}")
        
        return context

# Global self-improvement engine
improvement_engine = SelfImprovementEngine()
