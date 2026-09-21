"""
Text-to-speech with the ElevenLabs API.

The browser never talks to ElevenLabs directly. It asks our backend (POST
/speak), and the backend calls ElevenLabs with the API key, which stays on the
server. The result is an MP3 that the frontend plays.

Voice is optional: without ELEVENLABS_API_KEY the app works as before and
/speak answers with a clear "not set up" message.
"""
import os

import httpx

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # a premade ElevenLabs voice
DEFAULT_MODEL_ID = "eleven_flash_v2_5"  # fast, and half the credits of the standard models
OUTPUT_FORMAT = "mp3_44100_128"


class VoiceNotConfigured(Exception):
    """ELEVENLABS_API_KEY is not set."""


class VoiceServiceError(Exception):
    """ElevenLabs could not be reached or returned an error."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


def synthesize(text: str) -> bytes:
    """Turn text into MP3 audio and return the bytes."""
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise VoiceNotConfigured()

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID
    model_id = os.environ.get("ELEVENLABS_MODEL_ID") or DEFAULT_MODEL_ID

    try:
        response = httpx.post(
            f"{ELEVENLABS_URL}/{voice_id}",
            params={"output_format": OUTPUT_FORMAT},
            headers={"xi-api-key": api_key, "Accept": "audio/mpeg"},
            json={"text": text, "model_id": model_id},
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        print(f"[voice] Could not reach ElevenLabs: {exc}")
        raise VoiceServiceError(
            "Could not reach the voice service. Please try again."
        )

    if response.status_code != 200:
        # Log the reason for debugging. Never log the API key.
        print(f"[voice] ElevenLabs error {response.status_code}: {response.text[:300]}")
        if response.status_code == 401:
            message = (
                "The voice service rejected the request. Check the ElevenLabs "
                "API key and that the monthly character limit isn't used up."
            )
        elif response.status_code == 429:
            message = "The voice service is busy right now. Please try again in a moment."
        elif response.status_code in (402, 403):
            message = "This voice isn't available on the current ElevenLabs plan."
        else:
            message = "Something went wrong generating the audio. Please try again."
        raise VoiceServiceError(message)

    return response.content
