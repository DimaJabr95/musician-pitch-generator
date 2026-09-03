"""
Musician Pitch-Angle Generator — backend

Single endpoint: POST /generate-pitch
Takes a free-text musician bio/update, asks Gemini to find 2-3 newsworthy
angles and draft one pitch email based on the strongest angle.

See /mnt/user-data/outputs/musician-pitch-generator-spec.md for the full spec.

Note: originally built against the Anthropic API, but switched to Gemini
(google-genai) to use Google AI Studio's free tier during development —
same prompt/response contract either way, only the client and model name
changed. See README.md for the full story.
"""
import concurrent.futures
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai.errors import APIError
from pydantic import BaseModel, Field

app = FastAPI(title="Musician Pitch-Angle Generator")

# Allow the local Next.js dev server to call this API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

MODEL = "gemini-3.6-flash"

SYSTEM_PROMPT = """You are a music PR assistant. Given a short bio or update about a \
musician, do two things:

1. Identify 2-3 distinct newsworthy angles in the text. A newsworthy angle needs a \
concrete peg a journalist can hook a story on — a specific event, an unusual \
contrast or tension, a "first" or "only," a timely occasion, or something the \
musician could be quoted giving an opinion on. It is NOT a restatement of the \
musician's achievements or a summary of how impressive their career is.
   - Bad angle (achievement summary): "Her 17 years of experience make her a \
respected figure in the regional music scene."
   - Good angle (has a peg): "As a Syrian violinist now performing in the UAE, she \
can speak to how audiences and venues differ across the two countries."
   Each angle should be one short sentence, written the way a journalist would \
describe a story idea to an editor — not the way a press release would describe \
the musician.
2. Draft ONE short pitch email (subject + body, under 150 words) based on the \
strongest of those angles, written for a music journalist or local press editor. \
Keep the tone direct and human, not salesy — avoid words like "leverages," \
"showcases," or "brings a unique blend of."

Respond with ONLY valid JSON, no other text, in exactly this shape:
{"angles": ["...", "...", "..."], "email_draft": {"subject": "...", "body": "..."}}
"""


class PitchRequest(BaseModel):
    bio: str = Field(..., min_length=20, max_length=4000)


class EmailDraft(BaseModel):
    subject: str
    body: str


class PitchResponse(BaseModel):
    angles: list[str]
    email_draft: EmailDraft


def _client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not set on the server.",
        )
  
    return genai.Client(
        api_key=api_key,
        http_options={"timeout": 30_000},  # milliseconds
    )


def call_gemini(bio: str) -> dict:
    """Call the Gemini API and return the parsed JSON response.

    Pulled out as its own function so it's easy to mock in tests and to
    reuse if we add retries/logging later.
    """
    client = _client()
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=bio,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
            },
        )
    except APIError as exc:
    
        print(f"[call_gemini] Gemini API error: {exc}")

        status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if status == 503:
            user_message = (
                "The AI service is under heavy load right now. "
                "Please wait a moment and try again."
            )
        elif status == 429:
            user_message = (
                "Too many requests right now. Please wait a moment and try again."
            )
        else:
            user_message = (
                "Something went wrong generating your pitch. Please try again."
            )
        raise HTTPException(status_code=502, detail=user_message)

    raw_text = response.text

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
      
        stripped = raw_text.strip().strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:]
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=502,
                detail="Gemini returned a response that wasn't valid JSON.",
            )


@app.post("/generate-pitch", response_model=PitchResponse)
def generate_pitch(request: PitchRequest) -> PitchResponse:

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(call_gemini, request.bio)
        try:
            data = future.result(timeout=30)
        except concurrent.futures.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail=(
                    "The AI service took too long to respond. "
                    "Please try again."
                ),
            )

    if "angles" not in data or "email_draft" not in data:
        raise HTTPException(
            status_code=502,
            detail="Gemini's response was missing expected fields.",
        )

    return PitchResponse(**data)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}