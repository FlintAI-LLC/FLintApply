import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  MIC_PERMISSION_DENIED,
  releaseMediaStream,
  requestMicrophoneStream,
} from "@/lib/voice/microphonePermission";

function fakeStream(): MediaStream {
  const tracks: MediaStreamTrack[] = [
    { stop: () => undefined } as MediaStreamTrack,
  ];
  return {
    getTracks: () => tracks,
  } as MediaStream;
}

describe("requestMicrophoneStream", () => {
  it("returns granted stream from getUserMedia", async () => {
    const stream = fakeStream();
    const result = await requestMicrophoneStream({
      getUserMedia: async () => stream,
    });
    assert.equal(result.ok, true);
    if (result.ok) assert.equal(result.stream, stream);
  });

  it("maps a denied prompt to the Allow / site-settings message", async () => {
    const result = await requestMicrophoneStream({
      getUserMedia: async () => {
        throw new DOMException("Permission denied", "NotAllowedError");
      },
    });
    assert.equal(result.ok, false);
    if (!result.ok) assert.equal(result.message, MIC_PERMISSION_DENIED);
  });

  it("maps a missing device", async () => {
    const result = await requestMicrophoneStream({
      getUserMedia: async () => {
        throw new DOMException("Requested device not found", "NotFoundError");
      },
    });
    assert.equal(result.ok, false);
    if (!result.ok) assert.match(result.message, /No microphone/i);
  });

  it("fails closed when getUserMedia is unavailable", async () => {
    const result = await requestMicrophoneStream(undefined);
    assert.equal(result.ok, false);
  });
});

describe("releaseMediaStream", () => {
  it("stops every track", () => {
    let stopped = 0;
    const stream = {
      getTracks: () => [
        { stop: () => { stopped += 1; } } as MediaStreamTrack,
        { stop: () => { stopped += 1; } } as MediaStreamTrack,
      ],
    } as MediaStream;
    releaseMediaStream(stream);
    assert.equal(stopped, 2);
  });
});
