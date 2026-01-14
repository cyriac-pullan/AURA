"""
Interactive hands-free test - Standalone version
Run this to test wake word detection
"""
import speech_recognition as sr
import time

print("="*60)
print("AURA Hands-Free Mode Test")
print("="*60)
print("\nSay 'AURA' followed by a command (e.g., 'Aura set brightness to 50')")
print("Or say 'AURA' and then wait for the prompt...\n")

WAKE_WORDS = ["aura", "hey aura", "ok aura", "ora", "or a"]

def check_wake_word(text):
    text_lower = text.lower()
    for wake in WAKE_WORDS:
        if wake in text_lower:
            return True
    return False

def extract_command(text):
    text_lower = text.lower()
    for wake in WAKE_WORDS:
        if wake in text_lower:
            idx = text_lower.find(wake)
            return text[idx + len(wake):].strip().lstrip(',.!? ')
    return ""

recognizer = sr.Recognizer()
recognizer.energy_threshold = 400
recognizer.dynamic_energy_threshold = True

awaiting_command = False

print("Starting... Speak now!\n")

for i in range(20):  # Run 20 listening cycles
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            
            if awaiting_command:
                print(">>> Waiting for your command...")
            else:
                print(">>> Listening for 'Aura'...")
            
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                print("    (timeout - no speech)")
                continue
            
            try:
                text = recognizer.recognize_google(audio)
                print(f"    Heard: '{text}'")
                
                if awaiting_command:
                    print(f"\n✅ COMMAND: {text}")
                    print("    Would execute this command now!\n")
                    awaiting_command = False
                    
                elif check_wake_word(text.lower()):
                    print("\n🎯 WAKE WORD DETECTED!")
                    
                    command = extract_command(text)
                    if command and len(command) > 3:
                        print(f"✅ INLINE COMMAND: {command}")
                        print("    Would execute this command now!\n")
                    else:
                        print("    Say your command now...\n")
                        awaiting_command = True
                else:
                    print("    (no wake word, waiting...)\n")
                    
            except sr.UnknownValueError:
                print("    (could not understand)")
            except sr.RequestError as e:
                print(f"    API Error: {e}")
                
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)

print("\nTest complete!")
