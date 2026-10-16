import type { LogEvent, LogEventName, LogLevel } from "./contracts/log-event";
import { validateLogEvent } from "./validate";

export type LogFields = Pick<LogEvent, "request_id" | "video_id"> & {
  level?: LogLevel;
  attrs?: LogEvent["attrs"];
};

/**
 * Writes one log line for `event`, validated against the log event contract.
 * Throws for an event outside the catalogue or an unknown field.
 */
export function log(event: LogEventName, fields: LogFields = {}): void {
  const { level = "info", attrs = {}, ...rest } = fields;
  const line = { ts: new Date().toISOString(), level, service: "worker", event, ...rest, attrs };
  const { valid, errors } = validateLogEvent(line);
  if (!valid) {
    throw new Error(`invalid log event: ${errors.join("; ")}`);
  }
  console.log(JSON.stringify(line));
}
