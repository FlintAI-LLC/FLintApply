import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { parseApiErrorDetail } from "@/lib/parseApiError";

describe("parseApiErrorDetail", () => {
  it("formats tailored lint field_errors into a readable message", () => {
    const { message, fieldErrors } = parseApiErrorDetail(
      {
        message: "Resume contains invalid bullets or skills",
        field_errors: [
          {
            field: "skills[24]",
            rule: "skill_is_sentence",
            original: "scripting (Python or Bash) for automation and tooling",
          },
        ],
      },
      422,
    );
    assert.equal(fieldErrors?.length, 1);
    assert.match(message, /skill_is_sentence/);
    assert.match(message, /scripting/);
  });
});
