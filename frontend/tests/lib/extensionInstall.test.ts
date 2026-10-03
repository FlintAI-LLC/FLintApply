import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  EXTENSION_INSTALL_PATH,
  chromeWebStoreUrl,
  extensionBetaDownloadUrl,
  extensionInstallMode,
} from "@/lib/extensionInstall";

describe("extensionInstall", () => {
  it("uses a stable in-app path", () => {
    assert.equal(EXTENSION_INSTALL_PATH, "/extension");
  });

  it("defaults to the public Chrome Web Store listing", () => {
    const prev = process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL;
    delete process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL;
    try {
      assert.match(chromeWebStoreUrl() ?? "", /chromewebstore\.google\.com\/detail\/flint-apply\//);
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
});
