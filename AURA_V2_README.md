# AURA v2 - Hands-Free Voice Assistant Architecture

## Overview

AURA v2 is a redesigned architecture that transforms AURA into a true hands-free, cost-efficient AI assistant similar to Jarvis or Alexa.

### Key Improvements

| Feature | v1 | v2 |
|---------|----|----|
| Wake word activation | ❌ | ✅ Offline detection |
| Continuous listening | ❌ | ✅ Always listening |
| Local command routing | ❌ | ✅ 85%+ commands local |
| LLM cost per command | ~500 tokens | **0 tokens** (local) |
| Response personality | LLM | **Local** (free) |

### Token Savings Estimate

| Command Type | v1 Tokens | v2 Tokens | Savings |
|--------------|-----------|-----------|---------|
| "Set brightness to 50" | ~500 | **0** | 100% |
| "Open Chrome" | ~500 | **0** | 100% |
| "Mute" | ~500 | **0** | 100% |
| "Play video on YouTube" | ~500 | **0** | 100% |
| "What is AI?" (question) | ~800 | ~300 | 62% |
| Ambiguous command | ~800 | ~100 | 87% |

**Expected savings: 85-95% reduction in API costs**

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           AURA v2 CONTROL FLOW                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌─────────┐    ┌─────────────┐    ┌───────────┐    ┌──────────────────┐   │
│   │  WAKE   │───▶│  SPEECH TO  │───▶│  INTENT   │───▶│  ROUTING         │   │
│   │  WORD   │    │    TEXT     │    │  ROUTER   │    │  DECISION        │   │
│   │ (local) │    │   (local)   │    │  (local)  │    │                  │   │
│   └─────────┘    └─────────────┘    └───────────┘    └────────┬─────────┘   │
│                                                                │              │
│                    ┌───────────────────────────────────────────┼──────────┐  │
│                    │                                           │          │  │
│                    ▼                                           ▼          ▼  │
│   ┌────────────────────────┐  ┌──────────────────────┐  ┌───────────────┐   │
│   │    LOCAL EXECUTION     │  │   GEMINI INTENT      │  │ GEMINI CHAT   │   │
│   │    (0 tokens)          │  │   (~100 tokens)      │  │ (~300 tokens) │   │
│   │                        │  │                      │  │               │   │
│   │  conf >= 0.85          │  │  conf 0.50-0.85      │  │ conversation  │   │
│   └────────────────────────┘  └──────────────────────┘  └───────────────┘   │
│                    │                     │                       │           │
│                    └─────────────────────┼───────────────────────┘           │
│                                          ▼                                   │
│                              ┌────────────────────┐                          │
│                              │   LOCAL TTS        │                          │
│                              │   (response)       │                          │
│                              └────────────────────┘                          │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## New Files

| File | Purpose |
|------|---------|
| `local_context.py` | Session memory without token cost |
| `response_generator.py` | Local personality responses |
| `intent_router.py` | **Critical**: Pre-LLM routing |
| `function_executor.py` | Execute mapped functions |
| `wake_word_detector.py` | Offline wake word detection |
| `voice_input.py` | STT with Vosk/Google |
| `aura_core.py` | Main control loop |
| `aura_v2_bridge.py` | Integration with existing widget |

---

## Integration Guide

### Option 1: Use the Bridge (Recommended)

Modify `aura_floating_widget/aura_widget.py`:

```python
# Add import at top
from aura_v2_bridge import aura_bridge

# In ProcessingThread.run(), replace the AI call with:
class ProcessingThread(QThread):
    def run(self):
        try:
            # AURA v2 intelligent routing
            response, success, used_gemini = aura_bridge.process(
                self.message, 
                self.context
            )
            
            self.finished.emit(response, self.message, success)
            
        except Exception as e:
            logging.error(f"Error: {e}")
            self.finished.emit(str(e), self.message, False)
```

### Option 2: Full Replacement

Use `aura_core.py` directly:

```python
from aura_core import AuraCore

core = AuraCore(user_name="Sir")
core.greet()  # "Good evening, Sir. Aura is online."

# Process commands
response = core.process_command("set brightness to 50")
print(response)  # "Brightness set to 50%."

# Check stats
core.print_stats()
```

---

## Routing Logic

The `IntentRouter` classifies commands with confidence scores:

| Confidence | Action | Tokens |
|------------|--------|--------|
| >= 0.85 | Local execution | **0** |
| 0.50-0.85 | Gemini intent-only | ~100 |
| < 0.50 | Gemini full reasoning | ~500 |
| conversation | Gemini chat | ~300 |

### How Routing Works

1. **Pattern Matching** (highest confidence): Regex patterns extract command + args
2. **Keyword Matching**: Known keywords trigger functions
3. **Fuzzy Matching**: Similar phrases matched with rapidfuzz
4. **Conversation Detection**: Questions/discussions routed to Gemini

---

## Adding New Commands

Edit `intent_router.py`:

```python
FUNCTION_REGISTRY = {
    "your_new_function": {
        "keywords": ["trigger1", "trigger2"],
        "patterns": [
            r"(?:verb)\s+(.+)",  # Capture groups become args
        ],
        "extractor": lambda m: {"arg_name": m.group(1)}
    },
}
```

Then add mapping in `function_executor.py`:

```python
if function_name == "your_new_function":
    func = getattr(self._windows_utils, "actual_function_name", None)
    return func, {"param": args.get("arg_name")}
```

---

## Hands-Free Setup (Optional)

For true always-listening experience:

1. **Install Vosk** (offline STT):
   ```bash
   pip install vosk
   # Download model from https://alphacephei.com/vosk/models
   ```

2. **Install OpenWakeWord** (offline wake detection):
   ```bash
   pip install openwakeword
   ```

3. **Run continuous mode**:
   ```python
   from voice_input import ContinuousVoiceInput
   from aura_core import process_voice_command, speak
   
   voice = ContinuousVoiceInput(wake_words=["aura", "hey aura"])
   voice.start(
       wake_callback=lambda: speak("Yes?"),
       command_callback=lambda cmd: speak(process_voice_command(cmd))
   )
   ```

---

## Performance Stats

```python
from aura_core import get_aura_core

core = get_aura_core()
# ... run commands ...

stats = core.get_stats()
print(f"Local commands: {stats['local_commands']}")
print(f"Tokens saved: ~{stats['tokens_saved']}")
print(f"Local %: {stats['local_percentage']:.1f}%")
```

---

## Testing

```bash
# Run tests
python test_aura_v2.py

# Expected output:
# [LOCAL ] set brightness to 50    -> set_brightness (conf: 0.95)
# [LOCAL ] mute                    -> mute_system_volume (conf: 0.95)
# [GEMINI] what is AI              -> conversation (conf: 0.95)
```

---

## Files Created

```
E:\agent\
├── aura_core.py              # Main control loop
├── aura_v2_bridge.py         # Widget integration
├── intent_router.py          # Local intent classification
├── function_executor.py      # Function execution
├── response_generator.py     # Local TTS responses  
├── local_context.py          # Session memory
├── wake_word_detector.py     # Wake word detection
├── voice_input.py            # Speech-to-text
├── test_aura_v2.py           # Test script
└── AURA_V2_README.md         # This file
```
