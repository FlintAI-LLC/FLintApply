import assert from "node:assert/strict";
import { describe, it } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ApplyOnEmployerSiteButton } from "@/components/session/ApplyOnEmployerSiteButton";

describe("ApplyOnEmployerSiteButton", () => {
  it("renders state D card without apply link", () => {
    const html = renderToStaticMarkup(<ApplyOnEmployerSiteButton jobPostingUrl={null} />);
    assert.match(html, /apply-on-employer-site-no-url/);
    assert.match(html, /No saved job link/);
    assert.doesNotMatch(html, /Apply on employer site/);
  });

  it("renders enabled greenhouse link for allowlisted URL", () => {
    const url = "https://boards.greenhouse.io/acme/jobs/1";
    const html = renderToStaticMarkup(<ApplyOnEmployerSiteButton jobPostingUrl={url} />);
    assert.match(html, new RegExp(`href="${url}"`));
    assert.match(html, /Apply on employer site/);
    assert.match(html, /will offer to autofill/);
  });

  it("renders state C label for SmartRecruiters", () => {
    const url = "https://jobs.smartrecruiters.com/acme/1";
    const html = renderToStaticMarkup(<ApplyOnEmployerSiteButton jobPostingUrl={url} />);
    assert.match(html, /Open job posting/);
    assert.match(html, /not on the autofill list yet/);
    assert.match(html, new RegExp(`href="${url}"`));
  });
});
