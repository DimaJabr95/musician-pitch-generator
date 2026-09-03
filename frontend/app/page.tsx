"use client";

import { SyntheticEvent, useState } from "react";

type EmailDraft = {
  subject: string;
  body: string;
};

type PitchResult = {
  angles: string[];
  email_draft: EmailDraft;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function CopyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <rect x="8" y="8" width="12" height="12" rx="1.5" />
      <path d="M4 16V5a1 1 0 0 1 1-1h11" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M4 12.5l5 5L20 7" />
    </svg>
  );
}

export default function Home() {
  const [bio, setBio] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error" | "done">(
    "idle",
  );
  const [errorMessage, setErrorMessage] = useState("");
  const [result, setResult] = useState<PitchResult | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleSubmit(event: SyntheticEvent) {
    event.preventDefault();
    setStatus("loading");
    setErrorMessage("");
    setCopied(false);

    try {
      const response = await fetch(`${API_URL}/generate-pitch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bio }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Something went wrong generating the pitch.");
      }

      const data: PitchResult = await response.json();
      setResult(data);
      setStatus("done");
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "Something went wrong.",
      );
      setStatus("error");
    }
  }

  async function handleCopy() {
    if (!result) return;
    const text = `Subject: ${result.email_draft.subject}\n\n${result.email_draft.body}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API unavailable — fail quietly, the text is still selectable.
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-[640px] flex-col px-6 py-16 sm:py-24">
      <header className="mb-12">
        <p
          className="mb-3 text-sm"
          style={{ color: "var(--brass-soft)", fontFamily: "var(--font-body)" }}
        >
          For musicians and the people who pitch for them
        </p>
        <h1
          className="text-4xl leading-[1.1] sm:text-5xl"
          style={{ fontFamily: "var(--font-display)", fontStyle: "italic" }}
        >
          Find the story in your update.
        </h1>
        <p
          className="mt-4 max-w-[46ch] text-base leading-relaxed"
          style={{ color: "var(--paper-dim)" }}
        >
          Paste a bio, a release, a gig — get the angles a journalist would
          actually care about, and a draft pitch to send them.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <textarea
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          placeholder="Dima is a Damascus-trained violinist based in Dubai, performing at weddings and private events. She recently played a fusion set blending classical violin with Arabic maqam at a Dubai gallery opening..."
          minLength={20}
          maxLength={4000}
          required
          rows={8}
          className="w-full resize-none rounded-sm border px-4 py-4 text-base leading-relaxed outline-none transition-colors focus:border-[var(--brass)]"
          style={{
            background: "var(--ink-soft)",
            borderColor: "var(--rule)",
            color: "var(--paper)",
          }}
        />

        <button
          type="submit"
          disabled={status === "loading" || bio.trim().length < 20}
          className="self-start rounded-sm px-6 py-3 text-sm font-medium transition-opacity disabled:opacity-40"
          style={{ background: "var(--brass)", color: "var(--ink)" }}
        >
          {status === "loading" ? (
            <span className="inline-flex items-center gap-2">
              Reading between the lines
              <span className="inline-flex gap-[2px]">
                <span className="h-1 w-1 animate-bounce rounded-full" style={{ background: "var(--ink)", animationDelay: "0ms" }} />
                <span className="h-1 w-1 animate-bounce rounded-full" style={{ background: "var(--ink)", animationDelay: "150ms" }} />
                <span className="h-1 w-1 animate-bounce rounded-full" style={{ background: "var(--ink)", animationDelay: "300ms" }} />
              </span>
            </span>
          ) : (
            "Find the angles"
          )}
        </button>
      </form>

      {status === "error" && (
        <p
          className="mt-6 border-l-2 pl-4 text-sm"
          style={{ borderColor: "#b85c5c", color: "#e0a5a5" }}
        >
          {errorMessage}
        </p>
      )}

      {status === "done" && result && (
        <section className="results-enter mt-14 flex flex-col gap-10">
          <div>
            <h2
              className="mb-4 text-lg"
              style={{ fontFamily: "var(--font-display)" }}
            >
              The angles
            </h2>
            <div className="flex flex-col gap-3">
              {result.angles.map((angle, i) => (
                <div
                  key={i}
                  className="rounded-sm border-l-2 py-3 pl-5 pr-4 text-[15px] leading-relaxed transition-colors"
                  style={{
                    borderColor: "var(--brass)",
                    background: "var(--ink-card)",
                  }}
                >
                  {angle}
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2
              className="mb-4 text-lg"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Draft pitch
            </h2>
            <div
              className="overflow-hidden rounded-sm border"
              style={{ borderColor: "var(--rule)" }}
            >
              <div
                className="flex items-center justify-between border-b px-5 py-3"
                style={{ borderColor: "var(--rule)", background: "var(--brass-dim)" }}
              >
                <p className="text-sm" style={{ color: "var(--paper-dim)" }}>
                  <span style={{ color: "var(--brass-soft)" }}>Subject: </span>
                  {result.email_draft.subject}
                </p>
                <button
                  onClick={handleCopy}
                  className="flex shrink-0 items-center gap-1.5 rounded-sm px-2.5 py-1.5 text-xs transition-colors"
                  style={{
                    color: copied ? "var(--brass-soft)" : "var(--paper-dim)",
                  }}
                >
                  {copied ? <CheckIcon /> : <CopyIcon />}
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
              <div className="px-5 py-5" style={{ background: "var(--ink-soft)" }}>
                <p className="whitespace-pre-wrap text-[15px] leading-relaxed">
                  {result.email_draft.body}
                </p>
              </div>
            </div>
            <p className="mt-3 text-sm" style={{ color: "var(--paper-dim)" }}>
              Review before sending — this is a starting draft, not a final one.
            </p>
          </div>
        </section>
      )}
    </main>
  );
}