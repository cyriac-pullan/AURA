"""
AURA v2 - Wake Word Detector
Offline wake word detection using OpenWakeWord or Porcupine.
Enables true hands-free operation without any keyboard input.
"""

import logging
import threading
import time
from typing import Callable, Optional, List
from dataclasses import dataclass

# Try to import audio libraries
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logging.warning("pyaudio not available. Install with: pip install pyaudio")

# Try to import OpenWakeWord (free, offline)
try:
    import openwakeword
    from openwakeword.model import Model as OWWModel
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False
    logging.info("OpenWakeWord not available. Install with: pip install openwakeword")

# Try to import Porcupine (free tier available)
try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False
    logging.info("Porcupine not available. Install with: pip install pvporcupine")


@dataclass
class WakeWordConfig:
    """Configuration for wake word detection"""
    wake_words: List[str] = None
    sensitivity: float = 0.5
    backend: str = "auto"  # auto, openwakeword, porcupine, keyword
    
    def __post_init__(self):
        if self.wake_words is None:
            self.wake_words = ["aura", "hey aura"]


class WakeWordDetector:
    """
    Offline wake word detection.
    Supports multiple backends with automatic fallback.
    """
    
    def __init__(self, config: WakeWordConfig = None):
        self.config = config or WakeWordConfig()
        self.is_listening = False
        self._callback: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Audio settings
        self.sample_rate = 16000
        self.frame_length = 512
        
        # Initialize backend
        self._backend = None
        self._init_backend()
    
    def _init_backend(self):
        """Initialize the wake word detection backend"""
        backend = self.config.backend
        
        if backend == "auto":
            # Try backends in order of preference
            if OPENWAKEWORD_AVAILABLE:
                backend = "openwakeword"
            elif PORCUPINE_AVAILABLE:
                backend = "porcupine"
            else:
                backend = "keyword"
        
        if backend == "openwakeword" and OPENWAKEWORD_AVAILABLE:
            try:
                # Download models if needed
                openwakeword.utils.download_models()
                # Use the "hey jarvis" model as it's similar to "hey aura"
                self._backend = OWWModel(
                    wakeword_models=["hey_jarvis_v0.1"],
                    inference_framework="onnx"
                )
                self._backend_type = "openwakeword"
                logging.info("WakeWordDetector: Using OpenWakeWord backend")
                return
            except Exception as e:
                logging.warning(f"Failed to initialize OpenWakeWord: {e}")
        
        if backend == "porcupine" and PORCUPINE_AVAILABLE:
            try:
                # Use built-in wake words (computer, jarvis, etc.)
                self._backend = pvporcupine.create(
                    keywords=["computer", "jarvis"],
                    sensitivities=[self.config.sensitivity] * 2
                )
                self._backend_type = "porcupine"
                logging.info("WakeWordDetector: Using Porcupine backend")
                return
            except Exception as e:
                logging.warning(f"Failed to initialize Porcupine: {e}")
        
        # Fallback to simple keyword matching (requires STT to be running)
        self._backend_type = "keyword"
        logging.info("WakeWordDetector: Using keyword matching fallback")
    
    def start(self, callback: Callable):
        """
        Start listening for wake words.
        
        Args:
            callback: Function to call when wake word is detected
        """
        if self.is_listening:
            return
        
        self._callback = callback
        self._stop_event.clear()
        self.is_listening = True
        
        if self._backend_type in ["openwakeword", "porcupine"]:
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            logging.info("WakeWordDetector: Started listening")
        else:
            logging.info("WakeWordDetector: Keyword mode - requires external STT")
    
    def stop(self):
        """Stop listening for wake words"""
        self._stop_event.set()
        self.is_listening = False
        
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        
        logging.info("WakeWordDetector: Stopped listening")
    
    def _listen_loop(self):
        """Main listening loop for audio-based detection"""
        if not PYAUDIO_AVAILABLE:
            logging.error("PyAudio not available for wake word detection")
            return
        
        try:
            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.frame_length
            )
            
            logging.info("WakeWordDetector: Audio stream opened")
            
            while not self._stop_event.is_set():
                try:
                    audio_data = stream.read(self.frame_length, exception_on_overflow=False)
                    
                    if self._backend_type == "openwakeword":
                        prediction = self._backend.predict(audio_data)
                        for model_name, scores in prediction.items():
                            if any(score > self.config.sensitivity for score in scores):
                                logging.info(f"Wake word detected: {model_name}")
                                if self._callback:
                                    self._callback()
                                # Brief pause to avoid multiple triggers
                                time.sleep(1.0)
                    
                    elif self._backend_type == "porcupine":
                        import struct
                        pcm = struct.unpack_from("h" * self.frame_length, audio_data)
                        keyword_index = self._backend.process(pcm)
                        if keyword_index >= 0:
                            logging.info(f"Wake word detected (index: {keyword_index})")
                            if self._callback:
                                self._callback()
                            time.sleep(1.0)
                
                except Exception as e:
                    logging.error(f"Audio processing error: {e}")
                    time.sleep(0.1)
            
            stream.stop_stream()
            stream.close()
            pa.terminate()
            
        except Exception as e:
            logging.error(f"Wake word detection error: {e}")
    
    def check_keyword(self, text: str) -> bool:
        """
        Check if text contains a wake word (for keyword matching mode).
        
        Args:
            text: Transcribed speech text
            
        Returns:
            True if wake word detected
        """
        text_lower = text.lower().strip()
        
        for wake_word in self.config.wake_words:
            if wake_word.lower() in text_lower:
                return True
            
            # Check for variations
            if text_lower.startswith("hey " + wake_word.replace("hey ", "")):
                return True
            if text_lower.startswith("ok " + wake_word.replace("ok ", "")):
                return True
        
        return False
    
    def __del__(self):
        """Cleanup on deletion"""
        self.stop()
        if hasattr(self, '_backend') and self._backend_type == "porcupine":
            try:
                self._backend.delete()
            except:
                pass


# Simple keyword-based detector for when no audio backend is available
class KeywordWakeDetector:
    """
    Simple keyword-based wake word detector.
    Works with any STT system - just check the transcribed text.
    """
    
    def __init__(self, wake_words: List[str] = None):
        self.wake_words = wake_words or ["aura", "hey aura", "ok aura"]
        self._normalize_wake_words()
    
    def _normalize_wake_words(self):
        """Normalize wake words for matching"""
        self.wake_words_normalized = [w.lower().strip() for w in self.wake_words]
    
    def check(self, text: str) -> bool:
        """
        Check if text contains a wake word.
        
        Args:
            text: Transcribed speech text
            
        Returns:
            True if wake word detected
        """
        text_lower = text.lower().strip()
        
        # Check for exact or substring match
        for wake_word in self.wake_words_normalized:
            if wake_word in text_lower:
                return True
        
        # Check for common variations
        variations = ["hey ", "ok ", "hi ", "hello "]
        base_word = self.wake_words_normalized[0].replace("hey ", "").replace("ok ", "")
        
        for var in variations:
            if text_lower.startswith(var + base_word):
                return True
        
        return False
    
    def extract_command(self, text: str) -> str:
        """
        Extract the command after the wake word.
        
        Args:
            text: Full transcribed text including wake word
            
        Returns:
            Command text (everything after wake word)
        """
        text_lower = text.lower().strip()
        
        for wake_word in self.wake_words_normalized:
            if wake_word in text_lower:
                # Find position after wake word
                idx = text_lower.find(wake_word)
                command = text[idx + len(wake_word):].strip()
                
                # Remove common filler words
                for filler in [", ", "please ", "can you ", "could you "]:
                    if command.lower().startswith(filler):
                        command = command[len(filler):]
                
                return command.strip()
        
        return text


# Global instance
wake_detector = KeywordWakeDetector()


def check_wake_word(text: str) -> bool:
    """Check if text contains wake word"""
    return wake_detector.check(text)


def extract_command_after_wake(text: str) -> str:
    """Extract command after wake word"""
    return wake_detector.extract_command(text)
