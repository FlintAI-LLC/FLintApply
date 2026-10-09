import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  EXTENSION_INSTALL_PATH,
  chromeWebStoreUrl,
  extensionBetaDownloadUrl,
  extensionInstallMode,
  isProductionAppEnv,
} from "@/lib/extensionInstall";

const DEFAULT_STORE =
  "https://chromewebstore.google.com/detail/flint-apply/lcgioikkofajhechkhgjoidmbmnbniji";

describe("extensionInstall", () => {
  it("uses a stable in-app path", () => {
    assert.equal(EXTENSION_INSTALL_PATH, "/extension");
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

  it("hides beta download on production app env", () => {
    const prevEnv = process.env.NEXT_PUBLIC_APP_ENV;
    const prevSite = process.env.NEXT_PUBLIC_SITE_URL;
    process.env.NEXT_PUBLIC_APP_ENV = "production";
    process.env.NEXT_PUBLIC_SITE_URL = "https://flintapply.com";
    try {
      assert.equal(isProductionAppEnv(), true);
      assert.equal(extensionBetaDownloadUrl(), null);
      assert.equal(extensionInstallMode(), "store");
    } finally {
      if (prevEnv !== undefined) process.env.NEXT_PUBLIC_APP_ENV = prevEnv;
      else delete process.env.NEXT_PUBLIC_APP_ENV;
      if (prevSite !== undefined) process.env.NEXT_PUBLIC_SITE_URL = prevSite;
      else delete process.env.NEXT_PUBLIC_SITE_URL;
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
