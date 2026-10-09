import { describe, it } from "node:test"
import assert from "node:assert/strict"
import {
  LANDING_NAV_LINKS,
  MOBILE_NAV_LINKS,
  NAV_PILLARS,
  landingNavHrefFromLocation,
  landingNavLinkIsActive,
  navPathIsActive,
  navPillarIsActive,
} from "@/components/nav/navPillars"

describe("navPillars", () => {
  it("uses Applications label instead of Tracker", () => {
    const jobs = NAV_PILLARS.find((p) => p.id === "jobs")
    assert.ok(jobs)
    const apps = jobs!.links.find((l) => l.href === "/tracker")
    assert.equal(apps?.label, "Applications")
  })

  it("mobile nav omits dashboard duplicate link", () => {
    assert.ok(!MOBILE_NAV_LINKS.some((l) => l.href === "/dashboard"))
  })

  it("desktop home pillar is labelled Dashboard", () => {
    const home = NAV_PILLARS.find((p) => p.id === "home")
    assert.equal(home?.label, "Dashboard")
  })

  it("does not expose placeholder nav links on mobile", () => {
    assert.ok(!MOBILE_NAV_LINKS.some((l) => l.href === "#"))
  })

  it("navPathIsActive matches dashboard hash anchors", () => {
    assert.equal(
      navPathIsActive("/dashboard", "/dashboard#tailored-resumes", "#tailored-resumes"),
      true,
    )
    assert.equal(navPathIsActive("/dashboard", "/dashboard", "#tailored-resumes"), false)
    assert.equal(navPathIsActive("/dashboard", "/dashboard", ""), true)
  })

  it("resume pillar includes tailored resumes dashboard link", () => {
    const resume = NAV_PILLARS.find((p) => p.id === "resume")
    assert.ok(resume?.links.some((l) => l.href === "/dashboard#tailored-resumes"))
  })

  it("navPathIsActive matches dashboard and nested routes", () => {
    assert.equal(navPathIsActive("/dashboard", "/dashboard"), true)
    assert.equal(navPathIsActive("/tracker/abc", "/tracker"), true)
    assert.equal(navPathIsActive("/jobs/setup", "/jobs/setup"), true)
    assert.equal(navPathIsActive("/jobs", "/jobs/setup"), false)
  })

  it("navPillarIsActive when any child link matches", () => {
    const jobs = NAV_PILLARS.find((p) => p.id === "jobs")!
    assert.equal(navPillarIsActive("/tracker", jobs), true)
    assert.equal(navPillarIsActive("/billing", jobs), false)
  })

  it("highlights only the resume pillar on profile, not dashboard", () => {
    const home = NAV_PILLARS.find((p) => p.id === "home")!
    const resume = NAV_PILLARS.find((p) => p.id === "resume")!
    assert.equal(navPillarIsActive("/profile", home), false)
    assert.equal(navPillarIsActive("/profile", resume), true)
  })

  it("does not treat live session pages as Tailor for a job", () => {
    assert.equal(navPathIsActive("/session/abc-123", "/session/new"), false)
    assert.equal(navPathIsActive("/session/new", "/session/new"), true)
  })

  it("landing nav highlights only the matching hash anchor", () => {
    assert.equal(landingNavLinkIsActive("/", "/#pricing", "#pricing"), true)
    assert.equal(landingNavLinkIsActive("/", "/#faq", "#pricing"), false)
    assert.equal(landingNavLinkIsActive("/", "/#faq", "#faq"), true)
    assert.equal(landingNavLinkIsActive("/", "/#pricing", ""), false)
    assert.equal(landingNavLinkIsActive("/checkup", "/checkup", ""), true)
    assert.equal(landingNavLinkIsActive("/checkup", "/#pricing", "#pricing"), false)
  })

  it("resolves the active landing nav href from the current location", () => {
    assert.equal(landingNavHrefFromLocation("/", "#pricing"), "/#pricing")
    assert.equal(landingNavHrefFromLocation("/", "#faq"), "/#faq")
    assert.equal(landingNavHrefFromLocation("/checkup"), "/checkup")
    assert.equal(landingNavHrefFromLocation("/"), null)
  })

  it("exposes pricing, FAQ, and CV Checkup for signed-out visitors", () => {
    assert.deepEqual(
      LANDING_NAV_LINKS.map((link) => link.label),
      ["Pricing", "FAQ", "CV Checkup"],
    )
  })
})
