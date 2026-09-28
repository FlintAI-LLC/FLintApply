import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  EXTENSION_INSTALL_PATH,
  extensionInstallMode,
} from "@/lib/extensionInstall";

describe("extensionInstall", () => {
  it("uses a stable in-app path", () => {
    assert.equal(EXTENSION_INSTALL_PATH, "/extension");
  });

  it("defaults to beta-manual when no public URLs are configured", () => {
    const prevStore = process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL;
    const prevZip = process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    delete process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL;
    delete process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    try {
      assert.equal(extensionInstallMode(), "beta-manual");
    } finally {
      if (prevStore !== undefined) process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL = prevStore;
      else delete process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL;
      if (prevZip !== undefined) process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL = prevZip;
      else delete process.env.NEXT_PUBLIC_EXTENSION_DOWNLOAD_URL;
    }
  });
});
