#!/usr/bin/env python3
"""
AURA Floating Widget - JARVIS-Style Desktop AI Assistant
A minimal, elegant, always-on-top floating widget with personality

Redesigned with:
- Sequential A-U-R-A letter fade-in animation at startup
- Minimal centered layout (Title → Pulsing Orb → Command Input)
- Smooth pulsing glow effect
"""

import sys
import os
import math
import random
import threading
import queue
from datetime import datetime

# Add parent directory for AURA imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PyQt5.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
        QLabel, QPushButton, QLineEdit, QTextEdit, QFrame,
        QGraphicsDropShadowEffect, QSystemTrayIcon, QMenu, QAction,
        QGraphicsOpacityEffect, QStackedWidget
    )
    from PyQt5.QtCore import (
        Qt, QTimer, QPropertyAnimation, QEasingCurve, 
        pyqtSignal, QObject, QPoint, QSize, QThread,
        QSequentialAnimationGroup, QParallelAnimationGroup
    )
    from PyQt5.QtGui import (
        QColor, QPainter, QBrush, QPen, QLinearGradient,
        QRadialGradient, QFont, QIcon, QPainterPath, QCursor
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt5 not found. Install with: pip install PyQt5")

# Import AURA components
try:
    from ai_client import ai_client
    from code_executor import executor
    from capability_manager import capability_manager
    from self_improvement import improvement_engine
    import windows_system_utils
    AURA_AVAILABLE = True
except ImportError as e:
    AURA_AVAILABLE = False
    print(f"AURA components not available: {e}")

# Try to import voice output (TTS)
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# Try to import voice input (Speech Recognition)
try:
    import speech_recognition as sr
    STT_AVAILABLE = True
except ImportError:
    STT_AVAILABLE = False
    print("Speech recognition not available. Install with: pip install SpeechRecognition")

VOICE_AVAILABLE = TTS_AVAILABLE  # For backward compatibility

# ═══════════════════════════════════════════════════════════════════════════════
# AURA v2 - Intelligent Routing (reduces LLM costs by 85%+)
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from aura_v2_bridge import aura_bridge
    from wake_word_detector import KeywordWakeDetector, check_wake_word, extract_command_after_wake
    AURA_V2_AVAILABLE = True
    print("AURA v2 intelligent routing enabled")
except ImportError as e:
    AURA_V2_AVAILABLE = False
    print(f"AURA v2 not available, using fallback: {e}")

# TTS Manager for proper voice output
try:
    from tts_manager import get_tts_manager, speak as tts_speak
    TTS_MANAGER_AVAILABLE = True
    print("TTS Manager loaded")
except ImportError:
    TTS_MANAGER_AVAILABLE = False
    tts_speak = None


class AuraPersonality:
    """AURA's JARVIS-like personality - witty, helpful, slightly sarcastic"""
    
    def __init__(self):
        self.user_name = "Sir"  # Can be customized
        self.mood = "helpful"  # helpful, witty, focused, concerned
        self.interaction_count = 0
        
    def get_greeting(self):
        hour = datetime.now().hour
        self.interaction_count += 1
        
        greetings = {
            "morning": [
                f"Good morning, {self.user_name}. All systems operational.",
                f"Rise and shine, {self.user_name}. Ready to assist.",
                f"Morning, {self.user_name}. What shall we accomplish today?",
            ],
            "afternoon": [
                f"Good afternoon, {self.user_name}. At your service.",
                f"Back for more, {self.user_name}? I'm ready.",
                f"Afternoon, {self.user_name}. How may I assist?",
            ],
            "evening": [
                f"Good evening, {self.user_name}. Systems online.",
                f"Evening, {self.user_name}. What do you need?",
                f"Ah, {self.user_name}. Ready when you are.",
            ]
        }
        
        if hour < 12:
            return random.choice(greetings["morning"])
        elif hour < 17:
            return random.choice(greetings["afternoon"])
        else:
            return random.choice(greetings["evening"])
    
    def get_acknowledgment(self):
        responses = [
            "On it.",
            "Processing now.",
            "Consider it done.",
            "Working on it.",
            "Executing.",
            "Right away.",
            "One moment.",
        ]
        return random.choice(responses)
    
    def get_success_response(self):
        responses = [
            "Done.",
            "Completed.",
            "Task executed.",
            "Finished.",
            "All done.",
            "Done and dusted.",
        ]
        return random.choice(responses)
    
    def get_error_response(self, error_type="general"):
        if error_type == "not_understood":
            return random.choice([
                "Didn't catch that. Try again?",
                "Could you rephrase?",
                "That's unclear. Elaborate?",
            ])
        elif error_type == "failed":
            return random.choice([
                "That didn't work.",
                "Hit a snag. Trying another approach.",
                "Error encountered.",
            ])
        else:
            return random.choice([
                "Something went wrong.",
                "An error occurred.",
                "Technical difficulties.",
            ])
    
    def get_thinking_response(self):
        responses = [
            "Thinking...",
            "Processing...",
            "Analyzing...",
            "Computing...",
            "Working...",
        ]
        return random.choice(responses)
    
    def get_farewell(self):
        return random.choice([
            f"Goodbye, {self.user_name}.",
            "Signing off.",
            f"Until next time, {self.user_name}.",
            "Going to standby.",
        ])
    
    def get_status_report(self):
        return f"""System Status:
• Neural networks: Online
• Interactions: {self.interaction_count}
• Status: Ready"""


class VoiceThread(QThread):
    """Background thread for text-to-speech - Uses TTS Manager"""
    
    def __init__(self, text):
        super().__init__()
        self.text = text
        
    def run(self):
        if not self.text:
            return
        
        # Use TTS Manager if available
        if TTS_MANAGER_AVAILABLE and tts_speak:
            tts_speak(self.text)
        elif TTS_AVAILABLE:
            # Fallback to direct pyttsx3
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty('rate', 175)
                engine.say(self.text)
                engine.runAndWait()
                engine.stop()
            except Exception as e:
                print(f"Voice error: {e}")



class SpeechRecognitionThread(QThread):
    """Background thread for speech recognition - voice input"""
    recognized = pyqtSignal(str)
    error = pyqtSignal(str)
    listening_started = pyqtSignal()
    listening_stopped = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.is_listening = False
        
    def run(self):
        if not STT_AVAILABLE:
            self.error.emit("Speech recognition not available.")
            return
            
        try:
            recognizer = sr.Recognizer()
            microphone = sr.Microphone()
            
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                self.listening_started.emit()
                self.is_listening = True
                
                try:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                except sr.WaitTimeoutError:
                    self.error.emit("No speech detected.")
                    self.listening_stopped.emit()
                    return
            
            self.listening_stopped.emit()
            self.is_listening = False
            
            try:
                text = recognizer.recognize_google(audio)
                self.recognized.emit(text)
            except sr.UnknownValueError:
                self.error.emit("Didn't catch that.")
            except sr.RequestError as e:
                self.error.emit(f"Service unavailable: {e}")
                
        except Exception as e:
            self.listening_stopped.emit()
            self.error.emit(f"Microphone error: {str(e)}")


class ProcessingThread(QThread):
    """Background thread for AI processing - AURA v2 with intelligent routing"""
    finished = pyqtSignal(str, str, bool)  # response, type, success
    
    def __init__(self, message, context):
        super().__init__()
        self.message = message
        self.context = context
        
    def run(self):
        # ═══════════════════════════════════════════════════════════════════
        # AURA v2: Use intelligent routing (saves 85%+ LLM tokens)
        # ═══════════════════════════════════════════════════════════════════
        if AURA_V2_AVAILABLE:
            try:
                response, success, used_gemini = aura_bridge.process(
                    self.message, 
                    self.context
                )
                
                # Log routing stats periodically
                stats = aura_bridge.get_stats()
                if stats['total_commands'] % 10 == 0 and stats['total_commands'] > 0:
                    print(f"AURA v2 Stats: Local={stats['local_commands']}, "
                          f"Gemini={stats['gemini_full']}, "
                          f"Saved={stats['tokens_saved']} tokens")
                
                msg_type = "success" if success else "error"
                self.finished.emit(response, msg_type, success)
                return
                
            except Exception as e:
                print(f"AURA v2 error, falling back: {e}")
                # Fall through to legacy processing
        
        # ═══════════════════════════════════════════════════════════════════
        # Legacy fallback (if AURA v2 not available)
        # ═══════════════════════════════════════════════════════════════════
        if not AURA_AVAILABLE:
            self.finished.emit(
                "AURA backend not available.",
                "warning",
                False
            )
            return
            
        try:
            code = ai_client.generate_code(self.message, self.context)
            
            if not code:
                self.finished.emit(
                    "Couldn't understand that.",
                    "error",
                    False
                )
                return
            
            exec_context = {'context': self.context, 'print': print}
            for attr_name in dir(windows_system_utils):
                if not attr_name.startswith('_'):
                    exec_context[attr_name] = getattr(windows_system_utils, attr_name)
            
            success, output, result = executor.execute(code, exec_context)
            
            if success:
                self.finished.emit(output or "Done.", "success", True)
            else:
                improved, msg, exec_output = improvement_engine.handle_execution_failure(
                    self.message, code, output
                )
                if improved:
                    self.finished.emit(exec_output or msg, "success", True)
                else:
                    self.finished.emit(output or "Task failed.", "error", False)
                    
        except Exception as e:
            self.finished.emit(str(e), "error", False)


class ContinuousListeningThread(QThread):
    """
    AURA v2: Continuous listening thread with wake word detection.
    Enables true hands-free operation.
    """
    wake_word_detected = pyqtSignal()
    command_recognized = pyqtSignal(str)
    status_update = pyqtSignal(str)
    error = pyqtSignal(str)
    listening_active = pyqtSignal(bool)  # Signal when actively listening
    
    def __init__(self, wake_words=None):
        super().__init__()
        self.wake_words = wake_words or ["aura", "hey aura", "ok aura"]
        self.is_running = False
        self.awaiting_command = False
        self._stop_requested = False
        
    def run(self):
        import sys
        
        if not STT_AVAILABLE:
            self.error.emit("Speech recognition not available")
            return
        
        self.is_running = True
        self._stop_requested = False
        
        print("[Hands-Free] Starting continuous listening...", flush=True)
        
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 400  # Slightly higher threshold
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8  # Shorter pause
        
        self.status_update.emit("Listening for 'Aura'...")
        
        loop_count = 0
        
        while self.is_running and not self._stop_requested:
            loop_count += 1
            try:
                with sr.Microphone() as source:
                    # Quick ambient adjustment
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    self.listening_active.emit(True)
                    
                    if loop_count % 5 == 1:  # Every 5th loop
                        print(f"[Hands-Free] Listening (loop {loop_count})...", flush=True)
                    
                    try:
                        # Listen with timeout
                        audio = recognizer.listen(
                            source, 
                            timeout=3.0,  # Wait up to 3 seconds for speech to start
                            phrase_time_limit=10.0  # Max 10 seconds per phrase
                        )
                        self.listening_active.emit(False)
                    except sr.WaitTimeoutError:
                        self.listening_active.emit(False)
                        continue  # No speech, keep listening
                    
                    # Try to recognize
                    try:
                        text = recognizer.recognize_google(audio)
                        text_lower = text.lower().strip()
                        print(f"[Hands-Free] Heard: '{text}'")
                        
                        if self.awaiting_command:
                            # We're waiting for a command after wake word
                            print(f"[Hands-Free] Command received: '{text}'")
                            self.awaiting_command = False
                            self.command_recognized.emit(text)
                            
                        elif self._check_wake_word(text_lower):
                            # Wake word detected!
                            print(f"[Hands-Free] Wake word detected in: '{text}'")
                            self.wake_word_detected.emit()
                            
                            # Check if command is included after wake word
                            command = self._extract_command(text)
                            if command and len(command) > 3:
                                # Command included after wake word
                                print(f"[Hands-Free] Inline command: '{command}'")
                                self.command_recognized.emit(command)
                            else:
                                # Wait for next utterance as command
                                print("[Hands-Free] Waiting for command...")
                                self.awaiting_command = True
                        else:
                            # Not a wake word, ignore
                            print(f"[Hands-Free] Ignored (no wake word): '{text}'")
                                
                    except sr.UnknownValueError:
                        pass  # Silent - speech not understood
                    except sr.RequestError as e:
                        print(f"[Hands-Free] API error: {e}")
                        self.error.emit(f"Recognition service error")
                        import time
                        time.sleep(1)  # Brief pause before retry
                        
            except OSError as e:
                # Microphone access error
                print(f"[Hands-Free] Microphone error: {e}")
                self.error.emit(f"Microphone error")
                import time
                time.sleep(2)
            except Exception as e:
                if not self._stop_requested:
                    print(f"[Hands-Free] Error: {e}")
                import time
                time.sleep(0.5)
        
        print("[Hands-Free] Stopped listening")
        self.status_update.emit("Hands-free stopped")
    
    def _check_wake_word(self, text: str) -> bool:
        """Check if text contains wake word"""
        text_lower = text.lower()
        for wake in self.wake_words:
            if wake.lower() in text_lower:
                return True
        # Also check common misrecognitions of "Aura"
        # Including Hindi/regional misrecognitions
        misrecognitions = [
            # Common English mishearings
            "tora", "hora", "ora", "or a", "ura", "aora", 
            "dora", "laura", "aura", "aurora", "euro",
            "aira", "era", "ara", "oreo", "aura's",
            # Hindi/Regional mishearings
            "hamara", "howrah", "porus", "bhanwra", "bhawra",
            "honour", "horror", "hora", "horra",
            # Other variations
            "arra", "awara", "awra", "aara", "ahura",
            "for a", "flora", "cora", "nora"
        ]
        for mis in misrecognitions:
            if mis in text_lower:
                return True
        return False
    
    def _extract_command(self, text: str) -> str:
        """Extract command after wake word"""
        text_lower = text.lower()
        
        # Check primary wake words first
        for wake in self.wake_words:
            wake_lower = wake.lower()
            if wake_lower in text_lower:
                idx = text_lower.find(wake_lower)
                cmd = text[idx + len(wake_lower):].strip()
                cmd = cmd.lstrip(',.!? ')
                return cmd
        
        # Check misrecognitions (same list as _check_wake_word)
        misrecognitions = [
            "tora", "hora", "ora", "or a", "ura", "aora", 
            "dora", "laura", "aurora", "euro", "aira", "era", "ara",
            "hamara", "howrah", "porus", "bhanwra", "bhawra",
            "honour", "horror", "horra", "arra", "awara", "awra",
            "for a", "flora", "cora", "nora"
        ]
        for mis in misrecognitions:
            if mis in text_lower:
                idx = text_lower.find(mis)
                cmd = text[idx + len(mis):].strip()
                cmd = cmd.lstrip(',.!? ')
                return cmd
        
        return text
    
    def stop(self):
        """Stop the continuous listening"""
        print("[Hands-Free] Stop requested")
        self._stop_requested = True
        self.is_running = False


class PulsingOrb(QWidget):
    """Smooth pulsing glow orb - centered, minimal animation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 300)
        
        # Animation state
        self.pulse_phase = 0
        self.state = "idle"  # idle, listening, processing
        self.glow_intensity = 0.6
        
        # Colors
        self.primary_color = QColor(0, 212, 255)  # Cyan
        self.secondary_color = QColor(123, 104, 238)  # Purple
        
        # Smooth animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(50)  # 20 FPS for smooth pulsing
        
    def set_state(self, state):
        self.state = state
        if state == "processing":
            self.timer.setInterval(30)  # Faster for processing
        elif state == "listening":
            self.timer.setInterval(40)
        else:
            self.timer.setInterval(50)
        
    def animate(self):
        self.pulse_phase += 0.08
        
        if self.state == "processing":
            self.glow_intensity = 0.5 + 0.4 * math.sin(self.pulse_phase * 3)
        elif self.state == "listening":
            self.glow_intensity = 0.6 + 0.3 * math.sin(self.pulse_phase * 2)
        else:
            # Smooth, calm pulsing for idle
            self.glow_intensity = 0.5 + 0.3 * math.sin(self.pulse_phase)
            
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = self.rect().center()
        
        # Outer glow layers (pulsing)
        for i in range(4):
            glow_radius = 35 + i * 10
            glow_opacity = (0.15 - i * 0.03) * self.glow_intensity
            
            glow_gradient = QRadialGradient(center, glow_radius)
            
            # Color shift based on state
            if self.state == "processing":
                hue_shift = int(self.pulse_phase * 30) % 360
                glow_color = QColor.fromHsv(hue_shift, 180, 255)
            elif self.state == "listening":
                glow_color = QColor(255, 100, 100)  # Red tint
            else:
                # Blend between cyan and purple
                blend = (math.sin(self.pulse_phase * 0.5) + 1) / 2
                r = int(self.primary_color.red() * (1 - blend) + self.secondary_color.red() * blend)
                g = int(self.primary_color.green() * (1 - blend) + self.secondary_color.green() * blend)
                b = int(self.primary_color.blue() * (1 - blend) + self.secondary_color.blue() * blend)
                glow_color = QColor(r, g, b)
            
            glow_color.setAlphaF(glow_opacity)
            glow_gradient.setColorAt(0, glow_color)
            glow_gradient.setColorAt(1, QColor(0, 0, 0, 0))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow_gradient)
            painter.drawEllipse(center, int(glow_radius), int(glow_radius))
        
        # Main orb gradient
        orb_size = 28 + 4 * math.sin(self.pulse_phase)
        gradient = QRadialGradient(center, orb_size)
        
        if self.state == "processing":
            hue_shift = int(self.pulse_phase * 50) % 360
            color1 = QColor.fromHsv(hue_shift, 200, 255)
            color2 = QColor.fromHsv((hue_shift + 60) % 360, 200, 200)
        else:
            color1 = self.primary_color
            color2 = self.secondary_color
            
        color1.setAlphaF(0.9)
        color2.setAlphaF(0.7)
        
        gradient.setColorAt(0, QColor(255, 255, 255, 220))
        gradient.setColorAt(0.3, color1)
        gradient.setColorAt(1, color2)
        
        painter.setBrush(gradient)
        painter.drawEllipse(center, int(orb_size), int(orb_size))
        
        # Inner bright core
        inner_gradient = QRadialGradient(center, 12)
        inner_gradient.setColorAt(0, QColor(255, 255, 255, 200))
        inner_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(inner_gradient)
        painter.drawEllipse(center, 12, 12)


class AuraLoadingScreen(QWidget):
    """Startup loading animation with sequential A-U-R-A letter fade-in"""
    animation_complete = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(600, 400)
        
        # Setup layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        
        # Letters container
        self.letters_container = QWidget()
        letters_layout = QHBoxLayout(self.letters_container)
        letters_layout.setSpacing(8)
        letters_layout.setAlignment(Qt.AlignCenter)
        
        # Create letter labels
        self.letters = []
        for char in "AURA":
            label = QLabel(char)
            label.setStyleSheet("""
                color: #00d4ff;
                font-family: 'Segoe UI', Arial;
                font-size: 48px;
                font-weight: bold;
                letter-spacing: 4px;
            """)
            label.setAlignment(Qt.AlignCenter)
            
            # Add opacity effect
            opacity_effect = QGraphicsOpacityEffect(label)
            opacity_effect.setOpacity(0)
            label.setGraphicsEffect(opacity_effect)
            
            self.letters.append((label, opacity_effect))
            letters_layout.addWidget(label)
        
        layout.addStretch()
        layout.addWidget(self.letters_container)
        layout.addStretch()
        
        # Animation index
        self.current_letter = 0
        self.fade_timer = QTimer()
        self.fade_timer.timeout.connect(self.animate_next_letter)
        
    def start_animation(self):
        """Start the sequential fade-in animation"""
        self.current_letter = 0
        # Reset all letters to invisible
        for label, effect in self.letters:
            effect.setOpacity(0)
        
        # Start animation after a brief delay
        QTimer.singleShot(200, self.animate_next_letter)
        
    def animate_next_letter(self):
        """Animate the next letter fading in"""
        if self.current_letter >= len(self.letters):
            # All letters done, emit complete signal after a pause
            QTimer.singleShot(500, self.animation_complete.emit)
            return
        
        label, opacity_effect = self.letters[self.current_letter]
        
        # Create fade-in animation
        animation = QPropertyAnimation(opacity_effect, b"opacity")
        animation.setDuration(300)  # 300ms per letter
        animation.setStartValue(0)
        animation.setEndValue(1)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # Move to next letter when this animation finishes
        self.current_letter += 1
        animation.finished.connect(lambda: QTimer.singleShot(100, self.animate_next_letter))
        
        animation.start()
        # Keep reference to prevent garbage collection
        self._current_animation = animation


class MiniOrb(QWidget):
    """Mini pulsing orb for collapsed mode - 200px"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        
        # Animation state
        self.pulse_phase = 0
        self.state = "idle"
        self.glow_intensity = 0.6
        
        # Colors
        self.primary_color = QColor(0, 212, 255)
        self.secondary_color = QColor(123, 104, 238)
        
        # Animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(50)
        
    def set_state(self, state):
        self.state = state
        
    def animate(self):
        self.pulse_phase += 0.08
        
        if self.state == "processing":
            self.glow_intensity = 0.5 + 0.4 * math.sin(self.pulse_phase * 3)
        else:
            self.glow_intensity = 0.5 + 0.3 * math.sin(self.pulse_phase)
            
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = self.rect().center()
        
        # Outer glow
        for i in range(4):
            glow_radius = 40 + i * 12
            glow_opacity = (0.15 - i * 0.03) * self.glow_intensity
            
            glow_gradient = QRadialGradient(center, glow_radius)
            
            if self.state == "processing":
                hue_shift = int(self.pulse_phase * 30) % 360
                glow_color = QColor.fromHsv(hue_shift, 180, 255)
            else:
                blend = (math.sin(self.pulse_phase * 0.5) + 1) / 2
                r = int(self.primary_color.red() * (1 - blend) + self.secondary_color.red() * blend)
                g = int(self.primary_color.green() * (1 - blend) + self.secondary_color.green() * blend)
                b = int(self.primary_color.blue() * (1 - blend) + self.secondary_color.blue() * blend)
                glow_color = QColor(r, g, b)
            
            glow_color.setAlphaF(glow_opacity)
            glow_gradient.setColorAt(0, glow_color)
            glow_gradient.setColorAt(1, QColor(0, 0, 0, 0))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow_gradient)
            painter.drawEllipse(center, int(glow_radius), int(glow_radius))
        
        # Main orb
        orb_size = 35 + 5 * math.sin(self.pulse_phase)
        gradient = QRadialGradient(center, orb_size)
        
        if self.state == "processing":
            hue_shift = int(self.pulse_phase * 50) % 360
            color1 = QColor.fromHsv(hue_shift, 200, 255)
            color2 = QColor.fromHsv((hue_shift + 60) % 360, 200, 200)
        else:
            color1 = self.primary_color
            color2 = self.secondary_color
            
        color1.setAlphaF(0.9)
        color2.setAlphaF(0.7)
        
        gradient.setColorAt(0, QColor(255, 255, 255, 220))
        gradient.setColorAt(0.3, color1)
        gradient.setColorAt(1, color2)
        
        painter.setBrush(gradient)
        painter.drawEllipse(center, int(orb_size), int(orb_size))
        
        # Inner core
        inner_gradient = QRadialGradient(center, 15)
        inner_gradient.setColorAt(0, QColor(255, 255, 255, 200))
        inner_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(inner_gradient)
        painter.drawEllipse(center, 15, 15)


class MiniOrbWidget(QWidget):
    """Mini orb widget - collapsed mode at top-right corner"""
    expand_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.init_ui()
        
    def init_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(220, 220)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Mini orb
        self.orb = MiniOrb()
        layout.addWidget(self.orb)
        
        # Position at top-right
        self.position_window()
        
        # Enable dragging
        self.dragging = False
        self.drag_position = QPoint()
        
    def position_window(self):
        """Position at top-right corner with 20px margin"""
        screen = QApplication.primaryScreen().geometry()
        x = screen.width() - self.width() - 20
        y = 20
        self.move(x, y)
        
    def set_state(self, state):
        self.orb.set_state(state)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Check if click is on the orb area (center)
            center = self.rect().center()
            click_pos = event.pos()
            distance = ((click_pos.x() - center.x())**2 + (click_pos.y() - center.y())**2)**0.5
            
            if distance < 80:  # Click on orb
                self.expand_requested.emit()
            else:
                # Start dragging
                self.dragging = True
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        self.dragging = False


class SettingsDialog(QWidget):
    """Settings dialog for API key configuration"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.init_ui()
        
    def init_ui(self):
        # Window properties
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(400, 280)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Container
        container = QFrame()
        container.setObjectName("settings_container")
        container.setStyleSheet("""
            #settings_container {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(15, 15, 35, 250),
                    stop:1 rgba(30, 30, 60, 250)
                );
                border: 1px solid rgba(0, 212, 255, 0.4);
                border-radius: 15px;
            }
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 15, 20, 20)
        container_layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        
        title = QLabel("⚙️ Settings")
        title.setStyleSheet("""
            color: #00d4ff;
            font-size: 18px;
            font-weight: bold;
            letter-spacing: 2px;
        """)
        header.addWidget(title)
        header.addStretch()
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 12px;
                color: white;
                font-size: 16px;
            }
            QPushButton:hover {
                background: rgba(255, 71, 87, 0.5);
            }
        """)
        header.addWidget(close_btn)
        
        container_layout.addLayout(header)
        
        # API Key input
        api_label = QLabel("Gemini API Key")
        api_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.7);
            font-size: 12px;
        """)
        container_layout.addWidget(api_label)
        
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Enter your API key...")
        self.api_input.setEchoMode(QLineEdit.Password)
        self.api_input.returnPressed.connect(self.save_api_key)
        self.api_input.setStyleSheet("""
            QLineEdit {
                background: rgba(0, 0, 0, 0.4);
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 10px;
                padding: 10px 15px;
                color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: rgba(0, 212, 255, 0.7);
            }
        """)
        input_layout.addWidget(self.api_input)
        
        save_btn = QPushButton("Save")
        save_btn.setFixedSize(70, 40)
        save_btn.clicked.connect(self.save_api_key)
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00d4ff, stop:1 #7b68ee
                );
                border: none;
                border-radius: 10px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00e5ff, stop:1 #9370db
                );
            }
        """)
        input_layout.addWidget(save_btn)
        
        container_layout.addLayout(input_layout)
        
        # Voice selection
        voice_label = QLabel("Voice")
        voice_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.7);
            font-size: 12px;
        """)
        container_layout.addWidget(voice_label)
        
        voice_layout = QHBoxLayout()
        voice_layout.setSpacing(10)
        
        # Get current voice preference
        current_voice = os.environ.get('AURA_VOICE', 'male').lower()
        
        self.male_btn = QPushButton("🔊 Male")
        self.male_btn.setFixedHeight(36)
        self.male_btn.clicked.connect(lambda: self.set_voice('male'))
        self.male_btn.setCheckable(True)
        self.male_btn.setChecked(current_voice == 'male')
        voice_layout.addWidget(self.male_btn)
        
        self.female_btn = QPushButton("🔊 Female")
        self.female_btn.setFixedHeight(36)
        self.female_btn.clicked.connect(lambda: self.set_voice('female'))
        self.female_btn.setCheckable(True)
        self.female_btn.setChecked(current_voice == 'female')
        voice_layout.addWidget(self.female_btn)
        
        self.update_voice_button_styles()
        
        container_layout.addLayout(voice_layout)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        container_layout.addWidget(self.status_label)
        
        layout.addWidget(container)
        
        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 212, 255, 60))
        shadow.setOffset(0, 0)
        container.setGraphicsEffect(shadow)
        
        # Enable dragging
        self.dragging = False
        self.drag_position = QPoint()
        
        # Load current key if exists
        self.load_current_key()
        
    def load_current_key(self):
        """Load current API key from .env file"""
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.startswith('GEMINI_API_KEY='):
                            key = line.split('=', 1)[1].strip()
                            if key and not key.startswith('#'):
                                # Show masked key
                                self.api_input.setPlaceholderText(f"Current: {key[:8]}...{key[-4:]}")
                                break
            except:
                pass
    
    def save_api_key(self):
        """Save API key to .env file"""
        api_key = self.api_input.text().strip()
        
        if not api_key:
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
            self.status_label.setText("Please enter an API key")
            return
        
        if not api_key.startswith('AIza'):
            self.status_label.setStyleSheet("color: #ffd700; font-size: 11px;")
            self.status_label.setText("Warning: Key should start with 'AIza'")
        
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        
        try:
            # Read existing content
            lines = []
            key_found = False
            
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
                
                # Update or add GEMINI_API_KEY
                for i, line in enumerate(lines):
                    if line.startswith('GEMINI_API_KEY='):
                        lines[i] = f'GEMINI_API_KEY={api_key}\n'
                        key_found = True
                        break
            
            if not key_found:
                lines.append(f'\nGEMINI_API_KEY={api_key}\n')
            
            # Write back
            with open(env_path, 'w') as f:
                f.writelines(lines)
            
            # Update environment variable
            os.environ['GEMINI_API_KEY'] = api_key
            
            self.status_label.setStyleSheet("color: #00ff88; font-size: 11px;")
            self.status_label.setText("✓ API key saved successfully!")
            
            # Close after delay
            QTimer.singleShot(1500, self.close)
            
        except Exception as e:
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
            self.status_label.setText(f"Error: {str(e)[:30]}")
    
    def set_voice(self, voice_type):
        """Set voice preference and save to .env"""
        self.male_btn.setChecked(voice_type == 'male')
        self.female_btn.setChecked(voice_type == 'female')
        self.update_voice_button_styles()
        
        # Save to .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        
        try:
            lines = []
            voice_found = False
            
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
                
                for i, line in enumerate(lines):
                    if line.startswith('AURA_VOICE='):
                        lines[i] = f'AURA_VOICE={voice_type}\n'
                        voice_found = True
                        break
            
            if not voice_found:
                lines.append(f'\nAURA_VOICE={voice_type}\n')
            
            with open(env_path, 'w') as f:
                f.writelines(lines)
            
            # Update environment variable
            os.environ['AURA_VOICE'] = voice_type
            
            self.status_label.setStyleSheet("color: #00ff88; font-size: 11px;")
            self.status_label.setText(f"✓ Voice set to {voice_type.title()}")
            
        except Exception as e:
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
            self.status_label.setText(f"Error: {str(e)[:30]}")
    
    def update_voice_button_styles(self):
        """Update button styles based on selection"""
        active_style = """
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00d4ff, stop:1 #7b68ee
                );
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 12px;
                font-weight: bold;
            }
        """
        inactive_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 8px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.2);
            }
        """
        
        self.male_btn.setStyleSheet(active_style if self.male_btn.isChecked() else inactive_style)
        self.female_btn.setStyleSheet(active_style if self.female_btn.isChecked() else inactive_style)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        self.dragging = False
    
    def showEvent(self, event):
        """Center on screen when shown"""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        super().showEvent(event)

class AuraFloatingWidget(QWidget):
    """Main floating widget window - Minimal JARVIS-style interface"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize personality
        self.personality = AuraPersonality()
        self.context = {
            "filename": None,
            "last_text": "",
            "session_start": datetime.now(),
            "command_count": 0
        }
        
        # Message queue and processing
        self.processing_thread = None
        self.voice_thread = None
        self.speech_thread = None
        self.is_listening = False
        self.is_collapsed = False
        
        # AURA v2: Hands-free continuous listening
        self.hands_free_mode = False
        self.continuous_listening_thread = None
        
        # Mini orb widget for collapsed mode
        self.mini_orb_widget = None
        
        # Setup UI
        self.init_ui()
        self.setup_tray_icon()
        
        # Start with loading animation
        self.show_loading_animation()
        
    def init_ui(self):
        # Window properties - frameless, transparent, always on top
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(600)  # Larger width
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(0)
        
        # Stacked widget for loading/main views
        self.stacked_widget = QStackedWidget()
        
        # Loading screen
        self.loading_screen = AuraLoadingScreen()
        self.loading_screen.animation_complete.connect(self.show_main_widget)
        
        # Main container
        self.main_container = QFrame()
        self.main_container.setObjectName("container")
        self.main_container.setStyleSheet("""
            #container {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(10, 10, 26, 240),
                    stop:1 rgba(25, 25, 50, 240)
                );
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 20px;
            }
        """)
        
        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(20, 15, 20, 20)
        container_layout.setSpacing(15)
        
        # Header with control buttons only
        header = QHBoxLayout()
        
        # Settings button (left side)
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.clicked.connect(self.open_settings)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 14px;
                color: white;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.3);
            }
        """)
        header.addWidget(self.settings_btn)
        
        # Collapse button (triangle)
        self.collapse_btn = QPushButton("◀")
        self.collapse_btn.setFixedSize(28, 28)
        self.collapse_btn.clicked.connect(self.collapse_to_orb)
        self.collapse_btn.setToolTip("Collapse to mini orb")
        self.collapse_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 14px;
                color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.3);
            }
        """)
        header.addWidget(self.collapse_btn)
        
        header.addStretch()
        
        # Control buttons
        self.minimize_btn = QPushButton("−")
        self.minimize_btn.setFixedSize(28, 28)
        self.minimize_btn.clicked.connect(self.toggle_minimize)
        self.minimize_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 14px;
                color: white;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.3);
            }
        """)
        header.addWidget(self.minimize_btn)
        
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.clicked.connect(self.hide_to_tray)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 14px;
                color: white;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 71, 87, 0.5);
            }
        """)
        header.addWidget(self.close_btn)
        
        container_layout.addLayout(header)
        
        # AURA Title (centered)
        self.title = QLabel("AURA")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("""
            color: #00d4ff;
            font-family: 'Segoe UI', Arial;
            font-size: 40px;
            font-weight: bold;
            letter-spacing: 11px;
        """)
        container_layout.addWidget(self.title)
        
        # Pulsing Orb (centered)
        orb_container = QHBoxLayout()
        orb_container.addStretch()
        self.orb = PulsingOrb()
        orb_container.addWidget(self.orb)
        orb_container.addStretch()
        container_layout.addLayout(orb_container)
        
        # Status label (minimal, below orb)
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.5);
            font-size: 11px;
            letter-spacing: 2px;
        """)
        container_layout.addWidget(self.status_label)
        
        container_layout.addSpacing(10)
        
        # Input area
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Speak or type command...")
        self.input_field.returnPressed.connect(self.send_command)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(0, 0, 0, 0.4);
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 12px;
                padding: 12px 18px;
                color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: rgba(0, 212, 255, 0.7);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.4);
            }
        """)
        input_layout.addWidget(self.input_field)
        
        # Microphone button
        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setFixedSize(44, 44)
        self.mic_btn.clicked.connect(self.toggle_voice_input)
        self.mic_btn.setToolTip("Click to speak")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 22px;
                color: white;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.3);
                border-color: rgba(0, 212, 255, 0.6);
            }
        """)
        input_layout.addWidget(self.mic_btn)
        
        # AURA v2: Hands-free mode button (continuous listening with wake word)
        self.hands_free_btn = QPushButton("👂")
        self.hands_free_btn.setFixedSize(44, 44)
        self.hands_free_btn.clicked.connect(self.toggle_hands_free_mode)
        self.hands_free_btn.setToolTip("Hands-free mode (say 'Aura' to activate)")
        self.hands_free_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(123, 104, 238, 0.3);
                border-radius: 22px;
                color: white;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(123, 104, 238, 0.3);
                border-color: rgba(123, 104, 238, 0.6);
            }
        """)
        input_layout.addWidget(self.hands_free_btn)
        
        # Send button
        self.send_btn = QPushButton("▶")
        self.send_btn.setFixedSize(44, 44)
        self.send_btn.clicked.connect(self.send_command)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00d4ff, stop:1 #7b68ee
                );
                border: none;
                border-radius: 22px;
                color: white;
                font-size: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00e5ff, stop:1 #9370db
                );
            }
            QPushButton:pressed {
                background: #00d4ff;
            }
        """)
        input_layout.addWidget(self.send_btn)
        
        container_layout.addLayout(input_layout)
        
        # Add both screens to stacked widget
        self.stacked_widget.addWidget(self.loading_screen)
        self.stacked_widget.addWidget(self.main_container)
        
        self.main_layout.addWidget(self.stacked_widget)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 212, 255, 80))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)
        
        # Enable dragging
        self.dragging = False
        self.drag_position = QPoint()
        
        # Position window
        self.position_window()
        
    def show_loading_animation(self):
        """Show the loading animation"""
        self.stacked_widget.setCurrentWidget(self.loading_screen)
        self.loading_screen.start_animation()
        
    def show_main_widget(self):
        """Transition from loading to main widget"""
        self.stacked_widget.setCurrentWidget(self.main_container)
        self.input_field.setFocus()
        # Speak greeting
        if VOICE_AVAILABLE:
            self.voice_thread = VoiceThread(self.personality.get_greeting())
            self.voice_thread.start()
        
    def position_window(self):
        """Position window at center of screen"""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def open_settings(self):
        """Open settings dialog"""
        self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.show()
    
    def collapse_to_orb(self):
        """Collapse widget to mini orb at top-right corner"""
        if self.is_collapsed:
            return
            
        self.is_collapsed = True
        
        # Create mini orb widget if not exists
        if self.mini_orb_widget is None:
            self.mini_orb_widget = MiniOrbWidget()
            self.mini_orb_widget.expand_requested.connect(self.expand_from_orb)
        
        # Sync orb state
        self.mini_orb_widget.set_state(self.orb.state)
        
        # Hide main widget and show mini orb
        self.hide()
        self.mini_orb_widget.show()
    
    def expand_from_orb(self):
        """Expand from mini orb back to full widget"""
        if not self.is_collapsed:
            return
            
        self.is_collapsed = False
        
        # Hide mini orb and show main widget
        if self.mini_orb_widget:
            self.mini_orb_widget.hide()
        
        # Reposition at center and show
        self.position_window()
        self.show()
        self.activateWindow()
        self.input_field.setFocus()
        
    def setup_tray_icon(self):
        """Setup system tray icon"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("AURA - Neural Interface")
        
        tray_menu = QMenu()
        
        show_action = QAction("Show AURA", self)
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()
        
    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_from_tray()
            
    def hide_to_tray(self):
        self.hide()
        self.tray_icon.showMessage(
            "AURA",
            "Double-click to bring me back.",
            QSystemTrayIcon.Information,
            2000
        )
        
    def show_from_tray(self):
        self.show()
        self.activateWindow()
        self.input_field.setFocus()
        
    def toggle_minimize(self):
        """Minimize to taskbar"""
        self.showMinimized()
        
    def quit_application(self):
        if VOICE_AVAILABLE:
            self.voice_thread = VoiceThread(self.personality.get_farewell())
            self.voice_thread.start()
        QTimer.singleShot(1500, QApplication.quit)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        self.dragging = False
        
    def set_status(self, text, status_type="normal"):
        """Update status label"""
        colors = {
            "normal": "rgba(255, 255, 255, 0.5)",
            "success": "#00ff88",
            "error": "#ff6b6b",
            "warning": "#ffd700",
            "processing": "#00d4ff",
        }
        color = colors.get(status_type, colors["normal"])
        self.status_label.setStyleSheet(f"""
            color: {color};
            font-size: 11px;
            letter-spacing: 2px;
        """)
        self.status_label.setText(text)
        
    def send_command(self):
        """Send command to AURA"""
        command = self.input_field.text().strip()
        if not command:
            return
            
        self.input_field.clear()
        self.context["command_count"] += 1
        
        # Check for exit commands
        if command.lower() in ['exit', 'quit', 'goodbye', 'bye']:
            self.quit_application()
            return
            
        # Check for status
        if command.lower() in ['status', 'how are you']:
            self.set_status("Systems Online", "success")
            if VOICE_AVAILABLE:
                self.voice_thread = VoiceThread(self.personality.get_status_report())
                self.voice_thread.start()
            return
            
        # Show processing
        self.set_status("Processing...", "processing")
        self.orb.set_state("processing")
        
        # Process in background
        self.processing_thread = ProcessingThread(command, self.context)
        self.processing_thread.finished.connect(self.on_processing_complete)
        self.processing_thread.start()
        
        # Auto-collapse to mini orb while processing
        self.collapse_to_orb()
        
    def on_processing_complete(self, response, msg_type, success):
        """Handle processing completion"""
        self.orb.set_state("idle")
        
        # Also update mini orb state if collapsed
        if self.is_collapsed and self.mini_orb_widget:
            self.mini_orb_widget.set_state("idle")
        
        if success:
            self.set_status("Done", "success")
            if VOICE_AVAILABLE:
                self.voice_thread = VoiceThread(self.personality.get_success_response())
                self.voice_thread.start()
        else:
            self.set_status("Error", "error")
        
        # Reset status after delay
        QTimer.singleShot(3000, lambda: self.set_status("Ready", "normal"))
    
    def toggle_voice_input(self):
        """Toggle voice input - start/stop listening"""
        if not STT_AVAILABLE:
            self.set_status("Voice unavailable", "error")
            return
            
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()
    
    def start_listening(self):
        """Start listening for voice input"""
        self.is_listening = True
        self.orb.set_state("listening")
        self.set_status("Listening...", "warning")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 71, 87, 0.5);
                border: 2px solid rgba(255, 71, 87, 0.8);
                border-radius: 22px;
                color: white;
                font-size: 18px;
            }
        """)
        
        self.speech_thread = SpeechRecognitionThread()
        self.speech_thread.recognized.connect(self.on_speech_recognized)
        self.speech_thread.error.connect(self.on_speech_error)
        self.speech_thread.listening_stopped.connect(self.stop_listening)
        self.speech_thread.start()
    
    def stop_listening(self):
        """Stop listening and reset UI"""
        self.is_listening = False
        self.orb.set_state("idle")
        self.set_status("Ready", "normal")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 22px;
                color: white;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.3);
                border-color: rgba(0, 212, 255, 0.6);
            }
        """)
    
    def on_speech_recognized(self, text):
        """Handle recognized speech"""
        self.stop_listening()
        self.input_field.setText(text)
        self.set_status(f"Heard: {text[:20]}...", "success")
        QTimer.singleShot(500, self.send_command)
    
    def on_speech_error(self, error_msg):
        """Handle speech recognition error"""
        self.stop_listening()
        self.set_status("Didn't catch that", "error")
        QTimer.singleShot(2000, lambda: self.set_status("Ready", "normal"))
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AURA v2: HANDS-FREE MODE - Continuous listening with wake word
    # ═══════════════════════════════════════════════════════════════════════════
    
    def toggle_hands_free_mode(self):
        """Toggle hands-free continuous listening mode"""
        if not STT_AVAILABLE:
            self.set_status("Voice unavailable", "error")
            return
        
        if self.hands_free_mode:
            self.stop_hands_free_mode()
        else:
            self.start_hands_free_mode()
    
    def start_hands_free_mode(self):
        """Start continuous listening with wake word detection"""
        self.hands_free_mode = True
        
        # Update UI
        self.set_status("Hands-free: Say 'Aura'", "success")
        self.hands_free_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 255, 136, 0.4);
                border: 2px solid rgba(0, 255, 136, 0.8);
                border-radius: 22px;
                color: white;
                font-size: 18px;
            }
        """)
        self.hands_free_btn.setToolTip("Hands-free mode ACTIVE - Click to stop")
        
        # Start continuous listening thread
        self.continuous_listening_thread = ContinuousListeningThread(
            wake_words=["aura", "hey aura", "ok aura"]
        )
        self.continuous_listening_thread.wake_word_detected.connect(self.on_wake_word_detected)
        self.continuous_listening_thread.command_recognized.connect(self.on_hands_free_command)
        self.continuous_listening_thread.status_update.connect(lambda s: self.set_status(s, "normal"))
        self.continuous_listening_thread.error.connect(self.on_hands_free_error)
        self.continuous_listening_thread.start()
        
        # Voice confirmation using TTS Manager
        if TTS_MANAGER_AVAILABLE:
            tts_speak("Hands-free mode activated. Say Aura to wake me.")
        elif VOICE_AVAILABLE:
            self.voice_thread = VoiceThread("Hands-free mode activated. Say Aura to wake me.")
            self.voice_thread.start()
    
    def stop_hands_free_mode(self):
        """Stop continuous listening"""
        self.hands_free_mode = False
        
        # Stop the thread
        if self.continuous_listening_thread:
            self.continuous_listening_thread.stop()
            self.continuous_listening_thread.quit()
            self.continuous_listening_thread.wait(2000)
            self.continuous_listening_thread = None
        
        # Reset UI
        self.set_status("Ready", "normal")
        self.orb.set_state("idle")
        self.hands_free_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(123, 104, 238, 0.3);
                border-radius: 22px;
                color: white;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(123, 104, 238, 0.3);
                border-color: rgba(123, 104, 238, 0.6);
            }
        """)
        self.hands_free_btn.setToolTip("Hands-free mode (say 'Aura' to activate)")
        
        # Voice confirmation using TTS Manager
        if TTS_MANAGER_AVAILABLE:
            tts_speak("Hands-free mode deactivated.")
        elif VOICE_AVAILABLE:
            self.voice_thread = VoiceThread("Hands-free mode deactivated.")
            self.voice_thread.start()
    
    def on_wake_word_detected(self):
        """Handle wake word detection - AURA heard her name"""
        self.orb.set_state("listening")
        self.set_status("Yes?", "success")
        
        # Voice acknowledgment using TTS Manager
        if TTS_MANAGER_AVAILABLE and AURA_V2_AVAILABLE:
            ack = aura_bridge.get_acknowledgment()
            tts_speak(ack)
        elif TTS_MANAGER_AVAILABLE:
            tts_speak("Yes?")
        elif VOICE_AVAILABLE:
            self.voice_thread = VoiceThread("Yes?")
            self.voice_thread.start()
    
    def on_hands_free_command(self, command):
        """Handle command from hands-free mode"""
        self.orb.set_state("processing")
        self.set_status(f"Processing: {command[:25]}...", "processing")
        
        # Put command in input field (for visibility)
        self.input_field.setText(command)
        
        # Process the command
        self.context["command_count"] += 1
        
        # Check for exit commands
        if command.lower() in ['exit', 'quit', 'goodbye', 'bye', 'stop listening']:
            self.stop_hands_free_mode()
            return
        
        # Process in background thread
        self.processing_thread = ProcessingThread(command, self.context)
        self.processing_thread.finished.connect(self.on_hands_free_complete)
        self.processing_thread.start()
    
    def on_hands_free_complete(self, response, msg_type, success):
        """Handle completion in hands-free mode"""
        self.orb.set_state("idle")
        
        if success:
            self.set_status("Done - Say 'Aura'", "success")
        else:
            self.set_status("Error - Say 'Aura'", "error")
        
        # Speak the response using TTS Manager
        if TTS_MANAGER_AVAILABLE and response:
            tts_speak(response)
        elif VOICE_AVAILABLE and response:
            self.voice_thread = VoiceThread(response)
            self.voice_thread.start()
        
        # Clear input and reset after delay
        self.input_field.clear()
        QTimer.singleShot(3000, lambda: self.set_status("Hands-free: Say 'Aura'", "success") if self.hands_free_mode else None)
    
    def on_hands_free_error(self, error_msg):
        """Handle error in hands-free mode"""
        print(f"Hands-free error: {error_msg}")
        # Don't show transient errors, they're usually timeout related


def main():
    if not PYQT_AVAILABLE:
        print("❌ PyQt5 is required for the floating widget.")
        print("   Install with: pip install PyQt5")
        return 1
        
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    widget = AuraFloatingWidget()
    widget.show()
    
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
