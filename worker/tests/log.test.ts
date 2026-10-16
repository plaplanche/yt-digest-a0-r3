import { afterEach, describe, expect, it, vi } from "vitest";
import type { LogEventName } from "../src/contracts/log-event";
import { log, type LogFields } from "../src/log";

describe("log", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("writes one JSON line", () => {
    const write = vi.spyOn(console, "log").mockImplementation(() => undefined);
    log("service.started", { request_id: "req-1", attrs: { version: "0.1.0" } });
    expect(write).toHaveBeenCalledTimes(1);
    const line: unknown = JSON.parse(String(write.mock.calls[0]?.[0]));
    expect(line).toEqual({
      ts: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/),
      level: "info",
      service: "worker",
      event: "service.started",
      request_id: "req-1",
      attrs: { version: "0.1.0" },
    });
  });

  it("throws on an event outside the catalogue", () => {
    const write = vi.spyOn(console, "log").mockImplementation(() => undefined);
    // @ts-expect-error the type system rejects the event too
    expect(() => log("transcript.leaked")).toThrow(/invalid log event/);
    expect(() => log("transcript.leaked" as LogEventName)).toThrow(/invalid log event/);
    expect(write).not.toHaveBeenCalled();
  });

  it("throws on an unknown field", () => {
    const write = vi.spyOn(console, "log").mockImplementation(() => undefined);
    // @ts-expect-error the type system rejects the field too
    expect(() => log("service.started", { text: "hello" })).toThrow(/invalid log event/);
    expect(() => log("service.started", { text: "hello" } as LogFields)).toThrow(/invalid log event/);
    expect(write).not.toHaveBeenCalled();
  });
});
