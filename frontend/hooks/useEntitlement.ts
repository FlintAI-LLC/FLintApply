"use client";

import { useEffect, useState } from "react";
import { getSubscriptionCurrent, type SubscriptionCurrentResponse } from "@/lib/api";
import { useLiveBackendAccessToken } from "@/hooks/useLiveBackendAccessToken";
import { isSubscriptionActive } from "@/lib/billing";

type Subscription = NonNullable<SubscriptionCurrentResponse["subscription"]>;

export interface Entitlement {
  /** null until the first fetch resolves, so callers can avoid flashing the wrong copy. */
  isSubscribed: boolean | null;
  /** Free plan: actions are billed to credits and Whisper/job search are unavailable. */
  isFreeUser: boolean;
  creditBalance: number | null;
  creditCap: number | null;
  creditsUsed: number | null;
  aiBudgetCapUsd: number | null;
  aiBudgetUsedUsd: number | null;
  subscription: Subscription | null;
  /** null limit means no per-period cap (Premium fair use). */
  whisperAvailable: boolean;
  loading: boolean;
}

const UNRESOLVED: Entitlement = {
  isSubscribed: null,
  isFreeUser: true,
  creditBalance: null,
  creditCap: null,
  creditsUsed: null,
  aiBudgetCapUsd: null,
  aiBudgetUsedUsd: null,
  subscription: null,
  whisperAvailable: false,
  loading: true,
};

/**
 * Single source of entitlement truth for client components.
 *
 * Several components previously hardcoded `isFreeUser` or re-implemented this
 * fetch, which meant subscribers were shown credit warnings for actions their
 * plan already covers.
 */
export function useEntitlement(): Entitlement {
  const { status, token, authLoading } = useLiveBackendAccessToken();
  const [state, setState] = useState<Entitlement>(UNRESOLVED);

  useEffect(() => {
    if (authLoading) {
      setState({ ...UNRESOLVED, loading: true });
      return;
    }
    if (!token || status !== "authenticated") {
      setState({ ...UNRESOLVED, loading: false });
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const data = await getSubscriptionCurrent(token);
        if (cancelled) return;
        const sub = data.subscription;
        const subscribed = !!sub && isSubscriptionActive(sub.status);
        setState({
          isSubscribed: subscribed,
          isFreeUser: !subscribed,
          creditBalance: data.credit_balance,
          creditCap: data.credit_cap ?? (subscribed ? sub?.resumes_limit ?? null : null),
          creditsUsed: data.credits_used ?? (subscribed ? sub?.resumes_used ?? null : null),
          aiBudgetCapUsd:
            typeof data.ai_budget_cap_usd === "number" ? data.ai_budget_cap_usd : null,
          aiBudgetUsedUsd:
            typeof data.ai_budget_used_usd === "number" ? data.ai_budget_used_usd : null,
          subscription: sub ?? null,
          whisperAvailable: subscribed,
          loading: false,
        });
      } catch {
        if (!cancelled) setState({ ...UNRESOLVED, loading: false });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, status, authLoading]);

  return state;
}
