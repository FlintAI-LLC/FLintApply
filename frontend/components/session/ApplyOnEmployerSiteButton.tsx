"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { EXTENSION_INSTALL_PATH } from "@/lib/extensionInstall";
import {
  applyEmployerSiteHelperCopy,
  applyEmployerSiteLabel,
  resolveApplyEmployerSiteStructural,
  showGetExtensionLink,
  toDisplayState,
} from "@/lib/applyOnEmployerSiteModel";
import { useFlintApplyExtensionInstalled } from "@/hooks/useFlintApplyExtensionInstalled";
import { cn } from "@/lib/utils";

interface Props {
  jobPostingUrl: string | null | undefined;
}

const primaryBtnCls =
  "inline-flex items-center gap-2 px-4 py-2.5 rounded-lg font-semibold text-sm transition-colors bg-amber-400 text-slate-900 hover:bg-amber-300";

const secondaryBtnCls =
  "inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-400 dark:border-slate-600 text-sm font-semibold text-slate-800 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700";

function GetExtensionLink() {
  return (
    <Link href={EXTENSION_INSTALL_PATH} className="font-medium text-amber-800 dark:text-amber-300 hover:underline">
      Get the extension
    </Link>
  );
}

export function ApplyOnEmployerSiteButton({ jobPostingUrl }: Props) {
  const extensionDetected = useFlintApplyExtensionInstalled();
  const { structural, href } = resolveApplyEmployerSiteStructural(jobPostingUrl);
  const state = toDisplayState(structural, extensionDetected);
  const label = applyEmployerSiteLabel(state);
  const helper = applyEmployerSiteHelperCopy({ state, extensionDetected });
  const extensionLink = showGetExtensionLink({ state, extensionDetected });

  if (state === "D") {
    return (
      <div
        className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 p-4 text-sm text-slate-600 dark:text-slate-400"
        data-testid="apply-on-employer-site-no-url"
      >
        <p className="font-semibold text-slate-800 dark:text-slate-200 mb-2">No saved job link</p>
        <p className="leading-relaxed">
          This session has no posting URL (pasted descriptions and some in-app saves do not store one).
          Open the real application page in Chrome with Flint Apply installed and signed in — autofill
          will offer your recent tailored resume. <GetExtensionLink />
        </p>
      </div>
    );
  }

  if (!href || !label) {
    return null;
  }

  const isPrimary = state === "A" || state === "B";

  return (
    <div data-testid="apply-on-employer-site">
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(isPrimary ? primaryBtnCls : secondaryBtnCls)}
      >
        <ExternalLink className="w-4 h-4" />
        {label}
      </a>
      {helper ? (
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
          {helper}
          {extensionLink ? (
            <>
              {" "}
              <GetExtensionLink />
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
