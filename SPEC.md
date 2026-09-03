# Musician Pitch-Angle Generator — Spec

## Problem
Independent musicians (and small publicists) struggle to identify what makes their update — a
new release, a performance, a collaboration — actually newsworthy, and then to translate that
into a pitch a journalist would open. This app automates the first draft of that process: find
the angle, write the pitch.

## User
A musician (or someone helping them with PR) who has a short update to share and wants a
starting point for outreach to music journalists or local press.

## Core flow
1. User pastes a free-text bio/update into a single text box (e.g. background, recent
   activity, upcoming event).
2. User clicks **Generate**.
3. Backend sends the text to the Claude API with a prompt asking it to:
   - identify 2–3 distinct newsworthy angles in the text
   - draft one short pitch email based on the strongest angle
4. Frontend displays:
   - the 2–3 angles (short, labeled)
   - the drafted email (editable/copyable)

## Inputs / Outputs
- **Input:** raw text (bio/update), submitted via form POST to `/generate-pitch`
- **Output (JSON):**
  ```json
  {
    "angles": ["...", "...", "..."],
    "email_draft": {
      "subject": "...",
      "body": "..."
    }
  }
  ```

## Stack
- Backend: Python + FastAPI, single `/generate-pitch` POST endpoint, calls Anthropic API
- Frontend: Next.js + TypeScript, one page: textarea → submit button → results view
- Tests: FastAPI endpoint tests (request validation, response shape) using mocked Claude
  responses so tests don't depend on live API calls

## Out of scope (explicitly not building)
- Sending the email (draft only — human sends it themselves)
- User accounts / auth / persistence (no database, no saved history)
- Journalist/outlet database or contact matching
- Multi-language support
- Styling polish beyond basic readability

## What "done" looks like
- Working end-to-end: paste text → get angles + draft email
- At least 2–3 backend tests passing
- Small, readable commit history (spec → backend → tests → frontend → polish)
- One documented instance in the PR/commit history of catching and correcting something the
  AI got wrong (e.g. an inaccurate angle, a tone mismatch, a broken response shape)
