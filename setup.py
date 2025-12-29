#!/usr/bin/env python3
"""
Setup script for the Advanced AI Assistant
"""

import os
import sys
import subprocess
from pathlib import Path

def install_requirements():
    """Install required packages"""
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        return False
    
    try:
        print("📦 Installing required packages...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ])
        print("✅ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        return False

def setup_environment():
    """Setup environment variables and configuration"""
    print("\n🔧 Environment Setup")
    print("=" * 30)
    
    # Check for API key
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("⚠️  No API key found in environment variables")
        print("\nTo use this assistant, you need to set up an API key:")
        print("1. Get an API key from Google AI Studio (https://aistudio.google.com/app/apikey)")
        print("2. Set the environment variable:")
        print("   Windows: set GEMINI_API_KEY=your_key_here")
        print("   Linux/Mac: export GEMINI_API_KEY=your_key_here")
        print("\nOr add it to your system environment variables permanently.")
        
        # Offer to set it temporarily
        key_input = input("\nEnter your API key now (or press Enter to skip): ").strip()
        if key_input:
            os.environ['GEMINI_API_KEY'] = key_input
            print("✅ API key set for this session")
        else:
            print("⚠️  You'll need to set the API key before running the assistant")
    else:
        print("✅ API key found in environment")
    
    return True

def create_desktop_shortcut():
    """Create a desktop shortcut (Windows only)"""
    if sys.platform != "win32":
        return
    
    try:
        import winshell
        from win32com.client import Dispatch
        
        desktop = winshell.desktop()
        shortcut_path = os.path.join(desktop, "AI Assistant.lnk")
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = sys.executable
        shortcut.Arguments = str(Path(__file__).parent / "assistant.py")
        shortcut.WorkingDirectory = str(Path(__file__).parent)
        shortcut.IconLocation = sys.executable
        shortcut.save()
        
        print("✅ Desktop shortcut created")
        
    except ImportError:
        print("ℹ️  Install pywin32 to create desktop shortcuts")
    except Exception as e:
        print(f"⚠️  Could not create desktop shortcut: {e}")

def run_tests():
    """Run basic tests to verify installation"""
    print("\n🧪 Running Tests")
    print("=" * 20)
    
    try:
        # Test imports
        print("Testing imports...")
        from config import config
        from ai_client import ai_client
        from code_executor import executor
        from capability_manager import capability_manager
        print("✅ All modules imported successfully")
        
        # Test configuration
        print("Testing configuration...")
        if config.validate_api_key():
            print("✅ API key validation passed")
        else:
            print("⚠️  API key validation failed - set GEMINI_API_KEY")
        
        # Test code executor
        print("Testing code executor...")
        success, output, result = executor.execute("print('Hello, World!')")
        if success and "Hello, World!" in output:
            print("✅ Code executor working")
        else:
            print("⚠️  Code executor test failed")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🤖 Advanced AI Assistant Setup")
    print("=" * 40)
    
    # Install requirements
    if not install_requirements():
        return 1
    
    # Setup environment
    if not setup_environment():
        return 1
    
    # Create desktop shortcut
    create_desktop_shortcut()
    
    # Run tests
    if not run_tests():
        print("\n⚠️  Some tests failed, but you can still try running the assistant")
    
    print("\n🎉 Setup Complete!")
    print("\nTo start the assistant:")
    print(f"   python {Path(__file__).parent / 'assistant.py'}")
    print("\nOr use the desktop shortcut if created.")
    
    # Ask if user wants to start now
    if input("\nStart the assistant now? (y/n): ").lower().startswith('y'):
        try:
            assistant_path = Path(__file__).parent / "assistant.py"
            subprocess.run([sys.executable, str(assistant_path)])
        except KeyboardInterrupt:
            print("\n👋 Setup completed")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
