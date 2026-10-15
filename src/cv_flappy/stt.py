import base64
import io
import json
import re
import threading
import urllib.error
import urllib.request
import uuid
import wave

import numpy as np

from .config import (
    GEMINI_KEY,
    GROQ_KEY,
    STT_DEVICE,
    STT_ENABLED,
    STT_GEMINI_MODEL,
    STT_GEMINI_URL,
    STT_GROQ_MODEL,
    STT_GROQ_URL,
    STT_LANGUAGE,
    STT_NORMALIZE,
    STT_PROMPT,
    STT_PROVIDER,
    STT_RECORD_SECONDS,
    STT_SAMPLE_RATE,
    STT_SILENCE_SECONDS,
    STT_SPEECH_THRESHOLD,
    STT_TIMEOUT,
)

_CHUNK_SECONDS = 0.1
_INT16_MAX = 32768.0

_GEMINI_SYSTEM = (
    "You transcribe short audio clips. Reply with only the spoken Czech "
    "first name, with no punctuation and no commentary."
)


def _encode_wav(pcm: np.ndarray, rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


def _multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = "----cvflappy" + uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        body += str(value).encode("utf-8") + b"\r\n"
    for name, (filename, data, content_type) in files.items():
        body += f"--{boundary}\r\n".encode()
        body += (
            f'Content-Disposition: form-data; name="{name}"; '
            f'filename="{filename}"\r\n'
        ).encode()
        body += f"Content-Type: {content_type}\r\n\r\n".encode()
        body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


class Listener:
    """Speech-to-text for name entry via Groq or Google AI Studio.

    Records from the microphone on a worker thread, then uploads the clip and
    reads the transcript. The pygame loop polls ``listening``/``done``/``level``
    and reads ``text``.
    """

    def __init__(self, enabled: bool = STT_ENABLED):
        self.enabled = enabled
        self.provider = STT_PROVIDER
        self._key = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._recording = False
        self._generation = 0
        self.text = ""
        self.listening = False
        self.done = False
        self.level = 0.0
        if not self.enabled:
            print("STT disabled.")
            return
        if self.provider == "groq":
            self._key = GROQ_KEY
            env_hint = "GROQ_KEY"
        elif self.provider == "gemini":
            self._key = GEMINI_KEY
            env_hint = "GEMINI_API_KEY"
        else:
            print(f"STT disabled: unknown provider {self.provider!r}.")
            self.enabled = False
            return
        if not self._key:
            print(f"STT disabled: no {self.provider} API key (set {env_hint}).")
            self.enabled = False
            return
        try:
            import sounddevice  # noqa: F401
        except Exception as exc:
            print(f"STT disabled: sounddevice unavailable ({exc}).")
            self.enabled = False

    def start(self) -> None:
        if not self.enabled:
            return
        self._generation += 1
        self._stop.set()
        if self._recording and self._thread is not None:
            self._thread.join(timeout=1.0)
        self._stop.clear()
        generation = self._generation
        self.text = ""
        self.done = False
        self.level = 0.0
        self.listening = True
        self._thread = threading.Thread(
            target=self._record, args=(generation,), daemon=True
        )
        self._thread.start()

    def cancel(self) -> None:
        self._generation += 1
        self._stop.set()
        if self._recording and self._thread is not None:
            self._thread.join(timeout=1.0)
        self.listening = False
        self.done = False
        self.level = 0.0

    def _record(self, generation: int) -> None:
        import sounddevice as sd

        chunk = max(1, int(STT_SAMPLE_RATE * _CHUNK_SECONDS))
        frames: list[np.ndarray] = []
        speech_started = False
        silence_chunks = 0
        silence_limit = max(1, int(STT_SILENCE_SECONDS / _CHUNK_SECONDS))
        max_chunks = max(1, int(STT_RECORD_SECONDS / _CHUNK_SECONDS))
        try:
            with sd.InputStream(
                samplerate=STT_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                device=STT_DEVICE,
            ) as stream:
                self._recording = True
                for _ in range(max_chunks):
                    if self._stop.is_set():
                        break
                    data, _overflowed = stream.read(chunk)
                    level = float(np.abs(data).mean()) / _INT16_MAX
                    self.level = level
                    frames.append(data.copy())
                    if level >= STT_SPEECH_THRESHOLD:
                        speech_started = True
                        silence_chunks = 0
                    elif speech_started:
                        silence_chunks += 1
                        if silence_chunks >= silence_limit:
                            break
        except Exception as exc:
            print(f"STT: microphone error ({exc}).")
        finally:
            self._recording = False
            self.level = 0.0

        if generation != self._generation:
            return
        if not frames:
            self.listening = False
            self.done = True
            return
        audio = np.concatenate(frames).astype(np.float32).flatten()
        if STT_NORMALIZE and audio.size:
            peak = float(np.max(np.abs(audio)))
            if peak > 1.0:
                audio = audio * (0.9 * _INT16_MAX / peak)
        pcm = np.clip(audio, -_INT16_MAX, _INT16_MAX - 1).astype(np.int16)
        if self.provider == "gemini":
            text = self._transcribe_gemini(pcm)
        else:
            text = self._transcribe_groq(pcm)
        if generation != self._generation:
            return
        self.text = self._clean(text)
        self.listening = False
        self.done = True

    def _transcribe_groq(self, pcm: np.ndarray) -> str:
        fields = {
            "model": STT_GROQ_MODEL,
            "language": STT_LANGUAGE,
            "response_format": "json",
        }
        if STT_PROMPT:
            fields["prompt"] = STT_PROMPT
        body, content_type = _multipart(
            fields,
            {"file": ("name.wav", _encode_wav(pcm, STT_SAMPLE_RATE), "audio/wav")},
        )
        request = urllib.request.Request(
            STT_GROQ_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": content_type,
            },
        )
        data = self._post(request)
        if isinstance(data, dict):
            return str(data.get("text", ""))
        return data if isinstance(data, str) else ""

    def _transcribe_gemini(self, pcm: np.ndarray) -> str:
        payload = {
            "systemInstruction": {"parts": [{"text": _GEMINI_SYSTEM}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "Přepiš jméno z audia."},
                        {
                            "inlineData": {
                                "mimeType": "audio/wav",
                                "data": base64.b64encode(
                                    _encode_wav(pcm, STT_SAMPLE_RATE)
                                ).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {"temperature": 0},
        }
        url = STT_GEMINI_URL.format(model=STT_GEMINI_MODEL)
        sep = "&" if "?" in url else "?"
        request = urllib.request.Request(
            f"{url}{sep}key={self._key}",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        data = self._post(request)
        if isinstance(data, dict):
            for candidate in data.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    if isinstance(part, dict) and part.get("text"):
                        return str(part["text"])
        return data if isinstance(data, str) else ""

    @staticmethod
    def _post(request: urllib.request.Request):
        try:
            with urllib.request.urlopen(request, timeout=STT_TIMEOUT) as response:
                raw = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            print(f"STT: API error {exc.code}: {detail}")
            return None
        except Exception as exc:
            print(f"STT: request failed ({exc}).")
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    @staticmethod
    def _clean(text: str) -> str:
        for line in text.splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if line:
                return line.strip(" .,!?;:'\"")
        return ""
