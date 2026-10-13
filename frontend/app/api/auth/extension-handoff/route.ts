import { NextResponse } from "next/server"
import { auth } from "@/auth"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

/** Mint a one-time code so the browser extension can adopt this web session. */
export async function POST() {
  const session = await auth()
  const token = session?.backendAccessToken
  if (!token || session?.error === "TokenExpired") {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 })
  }

  const res = await fetch(`${API_BASE}/api/auth/extension/web-handoff`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  })

  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    return NextResponse.json(body, { status: res.status })
  }
  return NextResponse.json(body)
}
