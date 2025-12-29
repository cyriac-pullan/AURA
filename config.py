import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

def load_env_file(env_path: Path = None):
    """Load environment variables from .env file"""
    if env_path is None:
        env_path = Path(__file__).parent / ".env"

    if env_path.exists():
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        os.environ[key] = value
            print(f"✅ Loaded environment variables from {env_path}")
        except Exception as e:
            print(f"⚠️ Error loading .env file: {e}")
    else:
        print(f"ℹ️ No .env file found at {env_path}")

# Load .env file when module is imported
load_env_file()

class Config:
    """Secure configuration management for the AI Assistant"""
    
    def __init__(self):
        self.config_dir = Path.home() / ".ai_assistant"
        self.config_file = self.config_dir / "config.json"
        self.logs_dir = self.config_dir / "logs"
        self.capabilities_file = self.config_dir / "capabilities.json"
        self.learning_file = self.config_dir / "learning_data.json"
        
        # Create directories if they don't exist
        self.config_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Load configuration
        self._config = self._load_config()
        
        # Setup logging
        self._setup_logging()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default"""
        default_config = {
            "api": {
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "base_url": None  # Not needed for Gemini direct API
            },
            "security": {
                "allowed_modules": [],  # Empty list = allow all modules
                "forbidden_functions": [],  # Empty list = allow all functions
                "max_code_length": 50000,  # Increased limit
                "execution_timeout": 120  # Increased timeout
            },
            "learning": {
                "auto_improve": True,
                "save_successful_functions": True,
                "max_learning_history": 10000,  # Increased history
                "aggressive_learning": True,  # New flag for aggressive learning
                "auto_install_packages": True  # Auto-install missing packages
            },
            "voice": {
                "enabled": True,
                "language": "en-US",
                "timeout": 5
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_config = json.load(f)
                # Merge with defaults for any missing keys
                merged_config = {**default_config, **saved_config}
                # Force update model to latest default if it's an old OpenRouter format
                if merged_config.get('api', {}).get('model', '').startswith('google/') or merged_config.get('api', {}).get('model') == 'google/gemini-2.0-flash-001':
                    merged_config['api']['model'] = default_config['api']['model']
                    merged_config['api']['provider'] = default_config['api']['provider']
                    self._save_config(merged_config)  # Save the updated config
                return merged_config
            except Exception as e:
                logging.error(f"Error loading config: {e}")
                return default_config
        else:
            # Save default config
            self._save_config(default_config)
            return default_config
    
    def _save_config(self, config: Dict[str, Any]):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving config: {e}")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_file = self.logs_dir / "assistant.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value using dot notation"""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self._save_config(self._config)

        # If updating allowed modules, also update the validator
        if key == 'security.allowed_modules':
            self._update_validator_modules(value)

    def _update_validator_modules(self, modules: list):
        """Update the code validator with new allowed modules"""
        try:
            from code_executor import executor
            if hasattr(executor, 'validator'):
                executor.validator.allowed_modules = set(modules)
                logging.info(f"Updated validator with {len(modules)} allowed modules")
        except Exception as e:
            logging.warning(f"Could not update validator modules: {e}")
    
    @property
    def api_key(self) -> Optional[str]:
        """Get API key from environment variable"""
        return os.getenv('GEMINI_API_KEY') or os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENAI_API_KEY')
    
    def validate_api_key(self) -> bool:
        """Validate that API key is available"""
        key = self.api_key
        if not key:
            logging.error("No API key found. Please set GEMINI_API_KEY environment variable.")
            print("❌ ERROR: No API key found.")
            print("   Please set GEMINI_API_KEY in your .env file")
            print("   Get your key from: https://aistudio.google.com/app/apikey")
            return False
        if len(key) < 20:  # Basic validation
            logging.error("API key appears to be invalid (too short).")
            print("❌ ERROR: API key appears to be invalid (too short).")
            print("   Please check your GEMINI_API_KEY in .env file")
            return False
        # Check if key starts with expected prefix for Gemini
        if not key.startswith('AIza'):
            logging.warning("API key format may be incorrect (expected 'AIza' prefix for Gemini API key)")
        return True

# Global config instance
config = Config()
