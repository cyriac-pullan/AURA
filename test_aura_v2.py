"""
AURA v2 - Quick Test Script
Tests the local intent routing and execution.
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

print("\n" + "="*60)
print("AURA v2 - Hands-Free Voice Assistant Test")
print("="*60 + "\n")

# Test intent router
print("[1] Testing Intent Router...")
from intent_router import classify_command

test_commands = [
    "set brightness to 50",
    "mute",
    "turn up the volume",
    "open chrome",
    "take a screenshot",
    "what is machine learning",
    "play despacito on youtube",
    "create folder named test",
]

for cmd in test_commands:
    result = classify_command(cmd)
    status = "LOCAL" if result.confidence >= 0.85 else "GEMINI" if result.confidence >= 0.5 else "FULL"
    print(f"  [{status:6}] {cmd:35} -> {result.function or 'conversation'} (conf: {result.confidence:.2f})")

print("\n[2] Testing Function Executor...")
from function_executor import execute_command

# Test a safe command
result = execute_command("mute_system_volume")
print(f"  mute_system_volume: {'SUCCESS' if result.success else 'FAILED'}")

result = execute_command("unmute_system_volume")
print(f"  unmute_system_volume: {'SUCCESS' if result.success else 'FAILED'}")

print("\n[3] Testing Response Generator...")
from response_generator import get_response_generator
rg = get_response_generator()

print(f"  Greeting: {rg.greeting()}")
print(f"  Acknowledgment: {rg.acknowledgment()}")
print(f"  Success: {rg.confirmation(True)}")
print(f"  Failure: {rg.confirmation(False)}")

print("\n[4] Testing Full Pipeline...")
from aura_core import AuraCore

core = AuraCore(user_name="Sir")

# Process a few commands
test_pipeline = [
    "set brightness to 60",
    "mute",
]

for cmd in test_pipeline:
    response = core.process_command(cmd)
    print(f"  '{cmd}' -> '{response}'")

print("\n[5] Statistics:")
stats = core.get_stats()
print(f"  Local commands: {stats['local_commands']}")
print(f"  Tokens saved: ~{stats['tokens_saved']}")
print(f"  Local percentage: {stats['local_percentage']:.1f}%")

print("\n" + "="*60)
print("AURA v2 Test Complete!")
print("="*60 + "\n")
