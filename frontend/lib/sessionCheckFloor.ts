export const SESSION_CHECK_FLOOR_MS = 10_000

interface FloorEntry<T> {
  startedAt: number
  result: Promise<T>
}

/**
 * Per-session floor for the hydration fetch. A repeat call inside the window
 * shares the earlier request instead of hitting the API again, so a remount or
 * effect re-run can never turn into a request storm.
 */
export class SessionCheckFloor<T> {
  private readonly entries = new Map<string, FloorEntry<T>>()

  constructor(
    private readonly floorMs: number = SESSION_CHECK_FLOOR_MS,
    private readonly now: () => number = Date.now,
  ) {}

  run(sessionId: string, fetcher: () => Promise<T>): Promise<T> {
    const existing = this.entries.get(sessionId)
    if (existing && this.now() - existing.startedAt < this.floorMs) {
      return existing.result
    }

    const result = fetcher()
    this.entries.set(sessionId, { startedAt: this.now(), result })
    // A failed fetch must not pin the error for the whole window.
    result.catch(() => {
      if (this.entries.get(sessionId)?.result === result) {
        this.entries.delete(sessionId)
      }
    })
    return result
  }

  /** Drop the cached result once server state is known to have changed. */
  invalidate(sessionId: string): void {
    this.entries.delete(sessionId)
  }
}
