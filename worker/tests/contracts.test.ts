import { describe, expect, it } from "vitest";
import type { LogEvent } from "../src/contracts/log-event";
import type { TranscriptResult } from "../src/contracts/transcript-result";
import { isLogEvent, isTranscriptResult, validateTranscriptResult } from "../src/validate";

const result: TranscriptResult = {
  video_id: "dQw4w9WgXcQ",
  status: "ok",
  lang: "fr",
  source: "manual",
  word_count: 3,
  truncated: false,
  sponsor_ratio: 0.125,
  pages: ["un deux trois"],
};

const logLine: LogEvent = {
  ts: "2026-10-16T08:30:00.123Z",
  level: "info",
  service: "worker",
  event: "service.started",
  attrs: { version: "0.1.0" },
};

describe("transcript result", () => {
  it("accepts a valid result", () => {
    expect(validateTranscriptResult(result)).toEqual({ valid: true, errors: [] });
  });

  it("accepts a result without transcript", () => {
    const none = { ...result, status: "no_transcript", lang: null, source: null, word_count: 0, sponsor_ratio: null, pages: [] };
    expect(isTranscriptResult(none)).toBe(true);
  });

  it.each([
    ["an extra field", { extra: 1 }],
    ["a short video_id", { video_id: "too-short" }],
    ["a video_id with a bad character", { video_id: "dQw4w9WgXc!" }],
    ["a bad status", { status: "done" }],
    ["a bad source", { source: "robot" }],
    ["a negative word_count", { word_count: -1 }],
    ["a fractional word_count", { word_count: 1.5 }],
    ["a sponsor_ratio above 1", { sponsor_ratio: 1.5 }],
  ])("rejects %s", (_, change) => {
    expect(isTranscriptResult({ ...result, ...change })).toBe(false);
  });

  it("rejects a missing field", () => {
    const missing: Partial<TranscriptResult> = { ...result };
    delete missing.lang;
    expect(isTranscriptResult(missing)).toBe(false);
  });
});

describe("log event", () => {
  it("accepts a valid line", () => {
    expect(isLogEvent(logLine)).toBe(true);
  });

  it.each([
    ["an unknown event", { event: "transcript.leaked" }],
    ["an extra field", { extra: "x" }],
    ["a bad level", { level: "fatal" }],
    ["a bad service", { service: "browser" }],
    ["a timestamp without milliseconds", { ts: "2026-10-16T08:30:00Z" }],
  ])("rejects %s", (_, change) => {
    expect(isLogEvent({ ...logLine, ...change })).toBe(false);
  });
});
