import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  EXTENSION_INSTALL_PATH,
  EXTENSION_RELEASE_VERSION,
  chromeWebStoreExtensionVersion,
  chromeWebStoreUrl,
  extensionBetaDownloadUrl,
  extensionBetaRecommendedOverStore,
  extensionBetaVersion,
  extensionInstallMode,
  isProductionAppEnv,
} from "@/lib/extensionInstall";

const DEFAULT_STORE =
  "https://chromewebstore.google.com/detail/flint-apply/lcgioikkofajhechkhgjoidmbmnbniji";

describe("extensionInstall", () => {
  it("uses a stable in-app path", () => {
    assert.equal(EXTENSION_INSTALL_PATH, "/extension");
  });

  it("defaults install guide version labels to EXTENSION_RELEASE_VERSION", () => {
    const prevStore = process.env.NEXT_PUBLIC_CHROME_WEB_STORE_EXTENSION_VERSION;
    const prevBeta = process.env.NEXT_PUBLIC_EXTENSION_BETA_VERSION;
    delete process.env.NEXT_PUBLIC_CHROME_WEB_STORE_EXTENSION_VERSION;
    delete process.env.NEXT_PUBLIC_EXTENSION_BETA_VERSION;
    try {
      assert.equal(chromeWebStoreExtensionVersion(), EXTENSION_RELEASE_VERSION);
      assert.equal(extensionBetaVersion(), EXTENSION_RELEASE_VERSION);
    } finally {
      if (prevStore !== undefined) process.env.NEXT_PUBLIC_CHROME_WEB_STORE_EXTENSION_VERSION = prevStore;
      else delete process.env.NEXT_PUBLIC_CHROME_WEB_STORE_EXTENSION_VERSION;
      if (prevBeta !== undefined) process.env.NEXT_PUBLIC_EXTENSION_BETA_VERSION = prevBeta;
      else delete process.env.NEXT_PUBLIC_EXTENSION_BETA_VERSION;
    }
  });

  it("defaults to the public Chrome Web Store listing", () => {
    const prev = process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL;
    delete process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL;
    try {
      assert.equal(chromeWebStoreUrl(), DEFAULT_STORE);
    } finally {
      if (prev !== undefined) process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL = prev;
    }
  });

  it("builds beta download URL from site origin when unset", () => {
    const prevSite = process.env.NEXT_PUBLIC_SITE_URL;
    const prevZip = process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    delete process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    process.env.NEXT_PUBLIC_SITE_URL = "https://flintapply.com";
    try {
      assert.equal(
        extensionBetaDownloadUrl(),
        "https://flintapply.com/downloads/flintapply-extension-beta.zip",
      );
      assert.equal(extensionInstallMode(), "download");
    } finally {
      if (prevSite !== undefined) process.env.NEXT_PUBLIC_SITE_URL = prevSite;
      else delete process.env.NEXT_PUBLIC_SITE_URL;
      if (prevZip !== undefined) process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL = prevZip;
      else delete process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    }
  });

  it("honors an explicit download URL on the site origin", () => {
    const prevSite = process.env.NEXT_PUBLIC_SITE_URL;
    const prevZip = process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    process.env.NEXT_PUBLIC_SITE_URL = "https://flintapply.com";
    process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL =
      "https://flintapply.com/downloads/custom-beta.zip";
    try {
      assert.equal(extensionBetaDownloadUrl(), "https://flintapply.com/downloads/custom-beta.zip");
      assert.equal(extensionInstallMode(), "download");
    } finally {
      if (prevSite !== undefined) process.env.NEXT_PUBLIC_SITE_URL = prevSite;
      else delete process.env.NEXT_PUBLIC_SITE_URL;
      if (prevZip !== undefined) process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL = prevZip;
      else delete process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    }
  });

  it("strips a trailing slash on SITE_URL", () => {
    const prevSite = process.env.NEXT_PUBLIC_SITE_URL;
    const prevZip = process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    delete process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    process.env.NEXT_PUBLIC_SITE_URL = "https://flintapply.com/";
    try {
      assert.equal(
        extensionBetaDownloadUrl(),
        "https://flintapply.com/downloads/flintapply-extension-beta.zip",
      );
    } finally {
      if (prevSite !== undefined) process.env.NEXT_PUBLIC_SITE_URL = prevSite;
      else delete process.env.NEXT_PUBLIC_SITE_URL;
      if (prevZip !== undefined) process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL = prevZip;
      else delete process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    }
  });

  it("rejects a malicious store URL override", () => {
    const prev = process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL;
    process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL = "javascript:alert(1)";
    try {
      assert.equal(chromeWebStoreUrl(), DEFAULT_STORE);
    } finally {
      if (prev !== undefined) process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL = prev;
      else delete process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL;
    }
  });

  it("rejects a beta zip URL on an untrusted host", () => {
    const prevSite = process.env.NEXT_PUBLIC_SITE_URL;
    const prevZip = process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    process.env.NEXT_PUBLIC_SITE_URL = "https://flintapply.com";
    process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL = "https://evil.example/malware.zip";
    try {
      assert.equal(
        extensionBetaDownloadUrl(),
        "https://flintapply.com/downloads/flintapply-extension-beta.zip",
      );
    } finally {
      if (prevSite !== undefined) process.env.NEXT_PUBLIC_SITE_URL = prevSite;
      else delete process.env.NEXT_PUBLIC_SITE_URL;
      if (prevZip !== undefined) process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL = prevZip;
      else delete process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    }
  });

  it("offers beta download on production during Chrome review lag", () => {
    const prevEnv = process.env.NEXT_PUBLIC_APP_ENV;
    const prevSite = process.env.NEXT_PUBLIC_SITE_URL;
    const prevRec = process.env.NEXT_PUBLIC_EXTENSION_BETA_RECOMMENDED;
    process.env.NEXT_PUBLIC_APP_ENV = "production";
    process.env.NEXT_PUBLIC_SITE_URL = "https://flintapply.com";
    delete process.env.NEXT_PUBLIC_EXTENSION_BETA_RECOMMENDED;
    try {
      assert.equal(isProductionAppEnv(), true);
      assert.equal(
        extensionBetaDownloadUrl(),
        "https://flintapply.com/downloads/flintapply-extension-beta.zip",
      );
      assert.equal(extensionInstallMode(), "download");
      assert.equal(extensionBetaRecommendedOverStore(), true);
    } finally {
      if (prevEnv !== undefined) process.env.NEXT_PUBLIC_APP_ENV = prevEnv;
      else delete process.env.NEXT_PUBLIC_APP_ENV;
      if (prevSite !== undefined) process.env.NEXT_PUBLIC_SITE_URL = prevSite;
      else delete process.env.NEXT_PUBLIC_SITE_URL;
      if (prevRec !== undefined) process.env.NEXT_PUBLIC_EXTENSION_BETA_RECOMMENDED = prevRec;
      else delete process.env.NEXT_PUBLIC_EXTENSION_BETA_RECOMMENDED;
    }
  });

  it("returns null beta URL and store mode when site origin is unset", () => {
    const prevSite = process.env.NEXT_PUBLIC_SITE_URL;
    const prevZip = process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    delete process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    delete process.env.NEXT_PUBLIC_SITE_URL;
    try {
      assert.equal(extensionBetaDownloadUrl(), null);
      assert.equal(extensionInstallMode(), "store");
      assert.equal(chromeWebStoreUrl(), DEFAULT_STORE);
    } finally {
      if (prevSite !== undefined) process.env.NEXT_PUBLIC_SITE_URL = prevSite;
      if (prevZip !== undefined) process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL = prevZip;
    }
  });
});
