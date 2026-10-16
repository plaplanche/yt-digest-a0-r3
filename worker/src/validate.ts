import { Validator, type Schema } from "@cfworker/json-schema";
import logEventSchema from "../../contracts/log-event.schema.json" with { type: "json" };
import transcriptResultSchema from "../../contracts/transcript-result.schema.json" with { type: "json" };
import type { LogEvent } from "./contracts/log-event";
import type { TranscriptResult } from "./contracts/transcript-result";

// Runtime checks against the schemas in contracts/, the same files the types are generated from.

export interface Validation {
  valid: boolean;
  errors: string[];
}

function validator(schema: object): (value: unknown) => Validation {
  const compiled = new Validator(schema as Schema, "2020-12", false);
  return (value) => {
    const result = compiled.validate(value);
    return { valid: result.valid, errors: result.errors.map((e) => `${e.instanceLocation}: ${e.error}`) };
  };
}

export const validateTranscriptResult = validator(transcriptResultSchema);
export const validateLogEvent = validator(logEventSchema);

export function isTranscriptResult(value: unknown): value is TranscriptResult {
  return validateTranscriptResult(value).valid;
}

export function isLogEvent(value: unknown): value is LogEvent {
  return validateLogEvent(value).valid;
}
