"""
AURA v2 - Voice Input (Speech-to-Text)
Offline speech recognition using Vosk or online using Google.
Continuous listening with silence detection.
"""

import logging
import threading
import queue
import time
from typing import Optional, Callable
from dataclasses import dataclass

# Try to import audio libraries
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logging.warning("pyaudio not available")

# Try to import Vosk (offline, free)
try:
    import vosk
    import json
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    logging.info("Vosk not available. Install with: pip install vosk")

# Try to import SpeechRecognition (online options)
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    logging.info("SpeechRecognition not available. Install with: pip install SpeechRecognition")


@dataclass
class TranscriptionResult:
    """Result of speech transcription"""
    text: str
    confidence: float = 1.0
    is_final: bool = True
    duration: float = 0.0


class VoiceInput:
    """
    Voice input with multiple backend support.
    Priority: Vosk (offline) > SpeechRecognition (online)
    """
    
    def __init__(self, backend: str = "auto"):
        """
        Initialize voice input.
        
        Args:
            backend: "auto", "vosk", "google", "sphinx"
        """
        self.backend = backend
        self._recognizer = None
        self._vosk_model = None
        self._is_listening = False
        self._stop_event = threading.Event()
        
        # Audio settings
        self.sample_rate = 16000
        self.chunk_size = 4000
        
        self._init_backend()
    
    def _init_backend(self):
        """Initialize the STT backend"""
        if self.backend == "auto":
            if VOSK_AVAILABLE:
                self.backend = "vosk"
            elif SR_AVAILABLE:
                self.backend = "google"
            else:
                logging.error("No STT backend available!")
                return
        
        if self.backend == "vosk" and VOSK_AVAILABLE:
            try:
                # Try to load a small English model
                # User needs to download: https://alphacephei.com/vosk/models
                model_paths = [
                    "vosk-model-small-en-us-0.15",
                    "vosk-model-en-us-0.22",
                    "model",
                    "vosk-model",
                ]
                
                for path in model_paths:
                    try:
                        self._vosk_model = vosk.Model(path)
                        logging.info(f"Vosk model loaded from: {path}")
                        break
                    except:
                        continue
                
                if self._vosk_model is None:
                    logging.warning("No Vosk model found. Download from: https://alphacephei.com/vosk/models")
                    self.backend = "google" if SR_AVAILABLE else None
                    
            except Exception as e:
                logging.warning(f"Failed to initialize Vosk: {e}")
                self.backend = "google" if SR_AVAILABLE else None
        
        if self.backend == "google" and SR_AVAILABLE:
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = 300
            self._recognizer.dynamic_energy_threshold = True
            logging.info("Using Google Speech Recognition (online)")
    
    def listen_once(self, timeout: float = 5.0, phrase_time_limit: float = 10.0) -> Optional[TranscriptionResult]:
        """
        Listen for a single phrase and return transcription.
        
        Args:
            timeout: How long to wait for speech to start
            phrase_time_limit: Maximum phrase duration
            
        Returns:
            TranscriptionResult or None if no speech detected
        """
        if self.backend == "vosk" and self._vosk_model:
            return self._listen_vosk(timeout, phrase_time_limit)
        elif self.backend == "google" and self._recognizer:
            return self._listen_google(timeout, phrase_time_limit)
        else:
            logging.error("No STT backend available")
            return None
    
    def _listen_vosk(self, timeout: float, phrase_time_limit: float) -> Optional[TranscriptionResult]:
        """Listen using Vosk (offline)"""
        if not PYAUDIO_AVAILABLE:
            logging.error("PyAudio required for Vosk")
            return None
        
        try:
            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            rec = vosk.KaldiRecognizer(self._vosk_model, self.sample_rate)
            
            start_time = time.time()
            speech_detected = False
            silence_count = 0
            max_silence = 10  # ~1 second of silence to end
            
            full_text = ""
            
            while time.time() - start_time < phrase_time_limit:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "")
                    if text:
                        full_text += " " + text
                        speech_detected = True
                        silence_count = 0
                else:
                    partial = json.loads(rec.PartialResult())
                    if partial.get("partial", ""):
                        speech_detected = True
                        silence_count = 0
                    else:
                        silence_count += 1
                
                # End on silence after speech
                if speech_detected and silence_count > max_silence:
                    break
                
                # Timeout if no speech
                if not speech_detected and time.time() - start_time > timeout:
                    break
            
            # Get final result
            final = json.loads(rec.FinalResult())
            if final.get("text"):
                full_text += " " + final["text"]
            
            stream.stop_stream()
            stream.close()
            pa.terminate()
            
            full_text = full_text.strip()
            if full_text:
                return TranscriptionResult(
                    text=full_text,
                    confidence=0.9,
                    is_final=True,
                    duration=time.time() - start_time
                )
            
            return None
            
        except Exception as e:
            logging.error(f"Vosk listening error: {e}")
            return None
    
    def _listen_google(self, timeout: float, phrase_time_limit: float) -> Optional[TranscriptionResult]:
        """Listen using Google Speech Recognition (online)"""
        try:
            with sr.Microphone() as source:
                # Adjust for ambient noise
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                logging.info("Listening...")
                start_time = time.time()
                
                try:
                    audio = self._recognizer.listen(
                        source,
                        timeout=timeout,
                        phrase_time_limit=phrase_time_limit
                    )
                except sr.WaitTimeoutError:
                    return None
                
                try:
                    text = self._recognizer.recognize_google(audio)
                    return TranscriptionResult(
                        text=text,
                        confidence=0.95,
                        is_final=True,
                        duration=time.time() - start_time
                    )
                except sr.UnknownValueError:
                    return None
                except sr.RequestError as e:
                    logging.error(f"Google API error: {e}")
                    return None
                    
        except Exception as e:
            logging.error(f"Google listening error: {e}")
            return None
    
    def listen_continuous(self, callback: Callable[[TranscriptionResult], None]):
        """
        Start continuous listening with callback for each phrase.
        
        Args:
            callback: Function called with each transcription result
        """
        self._is_listening = True
        self._stop_event.clear()
        
        def listen_loop():
            while not self._stop_event.is_set():
                result = self.listen_once(timeout=2.0, phrase_time_limit=15.0)
                if result and result.text:
                    callback(result)
                time.sleep(0.1)
        
        self._listen_thread = threading.Thread(target=listen_loop, daemon=True)
        self._listen_thread.start()
    
    def stop_continuous(self):
        """Stop continuous listening"""
        self._is_listening = False
        self._stop_event.set()


class ContinuousVoiceInput:
    """
    Continuous voice input with wake word support.
    Listens constantly but only triggers on wake word.
    """
    
    def __init__(self, wake_words: list = None):
        self.voice_input = VoiceInput()
        self.wake_words = wake_words or ["aura", "hey aura", "ok aura"]
        self._is_running = False
        self._wake_callback: Optional[Callable] = None
        self._command_callback: Optional[Callable] = None
        
        # State
        self._awaiting_command = False
        self._command_timeout = 5.0
    
    def _check_wake_word(self, text: str) -> bool:
        """Check if text contains wake word"""
        text_lower = text.lower()
        return any(w.lower() in text_lower for w in self.wake_words)
    
    def _extract_command(self, text: str) -> str:
        """Extract command after wake word"""
        text_lower = text.lower()
        for wake in self.wake_words:
            if wake.lower() in text_lower:
                idx = text_lower.find(wake.lower())
                return text[idx + len(wake):].strip()
        return text
    
    def start(self, wake_callback: Callable, command_callback: Callable):
        """
        Start continuous listening.
        
        Args:
            wake_callback: Called when wake word detected
            command_callback: Called with command after wake word
        """
        self._wake_callback = wake_callback
        self._command_callback = command_callback
        self._is_running = True
        
        def process_speech(result: TranscriptionResult):
            if not result.text:
                return
            
            text = result.text.strip()
            
            if self._awaiting_command:
                # We're waiting for a command
                if self._command_callback:
                    self._command_callback(text)
                self._awaiting_command = False
            
            elif self._check_wake_word(text):
                # Wake word detected
                if self._wake_callback:
                    self._wake_callback()
                
                # Check if command is included
                command = self._extract_command(text)
                if command:
                    if self._command_callback:
                        self._command_callback(command)
                else:
                    self._awaiting_command = True
        
        self.voice_input.listen_continuous(process_speech)
    
    def stop(self):
        """Stop continuous listening"""
        self._is_running = False
        self.voice_input.stop_continuous()


# Global instance for easy access
voice_input = VoiceInput()


def listen_for_command(timeout: float = 5.0) -> Optional[str]:
    """Convenience function to listen for a single command"""
    result = voice_input.listen_once(timeout=timeout)
    return result.text if result else None
