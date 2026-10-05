"use client";

import { useSession } from "next-auth/react";
import {
  resolveBackendAuthState,
  type BackendAuthSessionStatus,
} from "@/lib/auth/accessToken";

/**
 * Backend JWT from the NextAuth session, omitting tokens past ``backendExpiresAt``.
 * ``authLoading`` is true while NextAuth or a silent refresh is catching up.
 */
export function useLiveBackendAccessToken() {
  const { data: session, status } = useSession();
  const authStatus = status as BackendAuthSessionStatus;
  const { token, pendingRefresh, authLoading } = resolveBackendAuthState(
    session,
    authStatus,
  );

  return { session, status, token, pendingRefresh, authLoading };
}
