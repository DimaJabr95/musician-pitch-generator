# Find the story

A small tool that takes a musician's bio or update and finds the newsworthy
angle in it, then drafts a pitch email a journalist would actually open.

Built as a scoped demo of AI-directed development: Python/FastAPI backend +
Next.js/TypeScript frontend, calling the Gemini API to do the actual
angle-finding and drafting.

See [`SPEC.md`](./SPEC.md) for the one-page spec this was built from.

## Why music

Real Pathos use case, scoped to a domain I actually know: a violinist's bio,
release, or performance update, in this repo's example.

## Running it locally

### Backend

```bash
cd backend
pip install -r requirements.txt
export GEMINI_API_KEY=your-key-here
uvicorn main:app --reload --port 8000
```

Get a free key at https://aistudio.google.com/apikey — no card required.

Run the tests (no API key needed — Gemini responses are mocked):

```bash
pytest
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000, paste a bio, click **Find the angles**.

## What's out of scope (see SPEC.md)

Sending the email, accounts/persistence, a journalist/outlet database,
multi-language support, and visual polish beyond basic readability.

## A note on process

The backend's `call_gemini` has one deliberate scar left in: the model
occasionally wraps its JSON response in a markdown code fence even with
`response_mime_type` set to JSON. Rather than silently accept that or
hide it, `main.py` strips and retries once, with a comment explaining
why. That's the "caught the AI getting something wrong" moment the spec
calls out.

This project started against the Anthropic API. I switched to Gemini
partway through after hitting a billing wall on a fresh Anthropic
console account — Google AI Studio's free tier has no card requirement
and no expiry, so it let me actually finish and test the app rather than
stall on unrelated account setup. The prompt/response contract and the
rest of the architecture are identical either way; only the client and
model name changed (see the diff in commit history).
