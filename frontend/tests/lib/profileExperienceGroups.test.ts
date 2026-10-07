import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  experienceJobGroupKey,
  groupExperienceChunksByJob,
  type ProfileChunk,
} from "@/lib/profile";

function chunk(
  id: string,
  metadata: Record<string, unknown>,
  content = "bullet",
): ProfileChunk {
  return {
    id,
    section_type: "experience",
    content,
    token_count: 10,
    metadata,
    created_at: null,
    updated_at: null,
  };
}

describe("experienceJobGroupKey", () => {
  it("combines company title and dates", () => {
    assert.equal(
      experienceJobGroupKey({ company: "Acme", title: "Engineer", dates: "2020–2022" }),
      "acme|engineer|2020–2022",
    );
  });

  it("returns empty when no company or title", () => {
    assert.equal(experienceJobGroupKey({ dates: "2020" }), "");
  });
});

describe("groupExperienceChunksByJob", () => {
  it("groups bullets under the same role", () => {
    const meta = { company: "Acme", title: "Engineer" };
    const { groups, ungrouped } = groupExperienceChunksByJob([
      chunk("a", meta, "Built APIs"),
      chunk("b", meta, "Led team"),
      chunk("c", {}, "orphan"),
    ]);
    assert.equal(groups.length, 1);
    assert.equal(groups[0]!.chunks.length, 2);
    assert.equal(ungrouped.length, 1);
    assert.match(groups[0]!.label, /Engineer/);
  });
});
