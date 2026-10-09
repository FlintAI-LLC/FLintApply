"use client"

import { useState, useRef, useEffect } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { signOut, useSession } from "next-auth/react"
import {
  ChevronDown,
  CreditCard,
  GraduationCap,
  LayoutDashboard,
  LifeBuoy,
  LogOut,
  Settings,
  UserCircle,
} from "lucide-react"
import type { NavPillar } from "@/components/nav/navPillars"
import { BrandLogo } from "@/components/brand/BrandLogo"
import {
  LANDING_NAV_LINKS,
  MOBILE_NAV_LINKS,
  NAV_PILLARS,
  landingNavHrefFromLocation,
  navPathIsActive,
  navPillarIsActive,
} from "@/components/nav/navPillars"
import { fetchMe, logoutUser } from "@/lib/auth/api"
import { liveBackendAccessToken } from "@/lib/auth/accessToken"
import { shouldShowUserMenu } from "@/lib/auth/navIdentity"
import { isSessionDead } from "@/lib/auth/refreshBackendSession"
import { needsEmailVerification } from "@/lib/auth/emailVerification"
import { clsx } from "clsx"
import { NotificationBell } from "@/components/nav/NotificationBell"
import { UsageWidget } from "@/components/nav/UsageWidget"
import { ThemeToggle } from "@/components/theme/ThemeToggle"
import { TutorialMenu } from "@/components/guidance/TutorialMenu"

export function NavBar() {
  const pathname = usePathname()
  const { data: session, status } = useSession()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [openPillarId, setOpenPillarId] = useState<string | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const pillarRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const pillarButtonRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const [pillarMenuPos, setPillarMenuPos] = useState<{
    left: number
    top: number
  } | null>(null)
  const [hadUserMenu, setHadUserMenu] = useState(false)
  const [activeLandingHref, setActiveLandingHref] = useState<string | null>(null)
  const [locationHash, setLocationHash] = useState("")

  const accessToken = liveBackendAccessToken(session)

  const showUserMenu = shouldShowUserMenu(status, session, isSessionDead())
  useEffect(() => {
    if (showUserMenu) {
      setHadUserMenu(true)
    } else if (status === "unauthenticated") {
      setHadUserMenu(false)
    }
  }, [showUserMenu, status])

  const renderUserMenu =
    showUserMenu || (status === "loading" && hadUserMenu)

  useEffect(() => {
    setActiveLandingHref(
      landingNavHrefFromLocation(pathname, window.location.hash),
    )
    setLocationHash(window.location.hash)
    const onHashChange = () => setLocationHash(window.location.hash)
    window.addEventListener("hashchange", onHashChange)
    return () => window.removeEventListener("hashchange", onHashChange)
  }, [pathname])

  useEffect(() => {
    setOpenPillarId(null)
    setPillarMenuPos(null)
  }, [pathname, locationHash])

  function updatePillarMenuPosition(pillarId: string) {
    const btn = pillarButtonRefs.current[pillarId]
    if (!btn) return
    const rect = btn.getBoundingClientRect()
    setPillarMenuPos({ left: rect.left, top: rect.bottom + 6 })
  }

  function togglePillarMenu(pillarId: string) {
    setOpenPillarId((current) => {
      const next = current === pillarId ? null : pillarId
      if (next) {
        requestAnimationFrame(() => updatePillarMenuPosition(next))
      } else {
        setPillarMenuPos(null)
      }
      return next
    })
  }

  useEffect(() => {
    if (openPillarId === null) return
    const pillarId = openPillarId
    function onLayout() {
      updatePillarMenuPosition(pillarId)
    }
    window.addEventListener("resize", onLayout)
    window.addEventListener("scroll", onLayout, true)
    return () => {
      window.removeEventListener("resize", onLayout)
      window.removeEventListener("scroll", onLayout, true)
    }
  }, [openPillarId])

  const openPillar = openPillarId
    ? NAV_PILLARS.find((pillar) => pillar.id === openPillarId)
    : null

  function isLandingNavActive(href: string) {
    return activeLandingHref === href
  }

  function handleLandingNavClick(href: string) {
    setActiveLandingHref(href)
  }

  useEffect(() => {
    if (!dropdownOpen) return
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [dropdownOpen])

  useEffect(() => {
    if (!openPillarId) return
    const activePillarId = openPillarId
    function handleClick(e: MouseEvent) {
      const root = pillarRefs.current[activePillarId]
      if (root && !root.contains(e.target as Node)) {
        setOpenPillarId(null)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [openPillarId])

  async function handleLogout() {
    setDropdownOpen(false)
    setHadUserMenu(false)
    try {
      if (session?.backendAccessToken) {
        await logoutUser(session.backendAccessToken)
      }
    } catch {
      // Continue with NextAuth sign-out even if backend call fails
    }
    await signOut({ callbackUrl: "/" })
  }

  function isActive(href: string) {
    return navPathIsActive(pathname, href, locationHash)
  }

  function pillarIsActive(pillar: (typeof NAV_PILLARS)[number]) {
    return navPillarIsActive(pathname, pillar, locationHash)
  }

  return (
    <nav className="border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-950/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 h-16 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
        <div className="flex items-center gap-2 min-w-0 overflow-hidden">
        <Link href={renderUserMenu ? "/dashboard" : "/"} className="flex items-center hover:opacity-90 transition-opacity shrink-0 py-1">
          <BrandLogo className="h-10 w-auto max-w-[120px] sm:max-w-[160px] lg:max-w-[200px] xl:max-w-[240px]" />
        </Link>

        {!renderUserMenu && (
          <div className="hidden sm:flex items-center gap-1 text-sm">
            {LANDING_NAV_LINKS.map((link) => (
              <NavLink
                key={link.href}
                href={link.href}
                active={isLandingNavActive(link.href)}
                onClick={() => handleLandingNavClick(link.href)}
              >
                {link.label}
              </NavLink>
            ))}
          </div>
        )}

        {renderUserMenu && (
          <div className="hidden md:flex items-center gap-0.5 text-sm text-slate-600 dark:text-slate-400 flex-1 min-w-0 overflow-x-auto overflow-y-hidden scrollbar-none px-1">
            {NAV_PILLARS.map((pillar) => {
              const pathActive = pillarIsActive(pillar)
              const open = openPillarId === pillar.id
              const singleLink =
                pillar.links.length === 1 ? pillar.links[0] : null

              if (singleLink) {
                return (
                  <NavLink key={pillar.id} href={singleLink.href} active={isActive(singleLink.href)}>
                    {pillar.label}
                  </NavLink>
                )
              }

              return (
                <PillarNavControl
                  key={pillar.id}
                  pillar={pillar}
                  pathActive={pathActive}
                  open={open}
                  buttonRef={(node) => {
                    pillarButtonRefs.current[pillar.id] = node
                  }}
                  rootRef={(node) => {
                    pillarRefs.current[pillar.id] = node
                  }}
                  onToggle={() => togglePillarMenu(pillar.id)}
                />
              )
            })}
          </div>
        )}

        {renderUserMenu && (
          <div className="md:hidden shrink-0">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-400/15 text-amber-900 dark:text-amber-200 text-sm font-medium"
            >
              <LayoutDashboard className="w-4 h-4" />
              Dashboard
            </Link>
          </div>
        )}
        </div>

        <div className="flex items-center gap-1 shrink-0 pl-1 relative z-20 bg-white/80 dark:bg-slate-950/80">
          {renderUserMenu && (
            <TutorialMenu showLabel={false} />
          )}
          <ThemeToggle showLabel={false} />
          {renderUserMenu && (
            <>
              <NotificationBell />
              <UsageWidget />
            </>
          )}
          {renderUserMenu ? (
            <UserMenu
              displayName={session!.backendUser?.display_name ?? session!.user?.name ?? "You"}
              email={session!.user?.email ?? ""}
              creditBalance={session!.backendUser?.credit_balance}
              accessToken={accessToken}
              emailNeedsVerification={needsEmailVerification(session!.backendUser)}
              dropdownOpen={dropdownOpen}
              setDropdownOpen={setDropdownOpen}
              dropdownRef={dropdownRef}
              onLogout={handleLogout}
            />
          ) : status === "authenticated" ? (
            <button
              type="button"
              onClick={() => void handleLogout()}
              className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 px-3 py-1.5"
            >
              Sign out
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/auth"
                className="text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 text-sm font-medium px-3 py-1.5 transition-colors"
              >
                Sign in
              </Link>
              <Link
                href="/auth?mode=register"
                className="bg-amber-400 text-slate-900 font-semibold text-sm px-4 py-1.5 rounded-lg hover:bg-amber-300 transition-colors"
              >
                Register
              </Link>
            </div>
          )}
        </div>
      </div>

      {openPillar && pillarMenuPos && (
        <PillarDropdownMenu
          pillar={openPillar}
          position={pillarMenuPos}
          isActive={isActive}
          onNavigate={() => {
            setOpenPillarId(null)
            setPillarMenuPos(null)
          }}
        />
      )}

      {renderUserMenu && (
        <div className="md:hidden border-t border-slate-200 dark:border-slate-800 px-2 py-2 flex gap-1 overflow-x-auto text-xs">
          {MOBILE_NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={clsx(
                "px-3 py-1.5 rounded-lg whitespace-nowrap shrink-0",
                isActive(href)
                  ? "bg-amber-400/20 text-amber-900 dark:text-amber-200 font-medium"
                  : "text-slate-600 dark:text-slate-400",
              )}
            >
              {label}
            </Link>
          ))}
        </div>
      )}

      {!renderUserMenu && (
        <div className="sm:hidden border-t border-slate-200 dark:border-slate-800 px-2 py-2 flex gap-1 overflow-x-auto text-xs">
          {LANDING_NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              onClick={() => handleLandingNavClick(href)}
              className={clsx(
                "px-3 py-1.5 rounded-lg whitespace-nowrap shrink-0",
                isLandingNavActive(href)
                  ? "bg-amber-400/20 text-amber-900 dark:text-amber-200 font-medium"
                  : "text-slate-600 dark:text-slate-400",
              )}
            >
              {label}
            </Link>
          ))}
        </div>
      )}
    </nav>
  )
}

function PillarNavControl({
  pillar,
  pathActive,
  open,
  onToggle,
  buttonRef,
  rootRef,
}: {
  pillar: NavPillar
  pathActive: boolean
  open: boolean
  onToggle: () => void
  buttonRef: (node: HTMLButtonElement | null) => void
  rootRef: (node: HTMLDivElement | null) => void
}) {
  return (
    <div className="relative shrink-0" ref={rootRef}>
      <button
        type="button"
        ref={buttonRef}
        onClick={onToggle}
        className={clsx(
          "inline-flex items-center gap-1 px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap",
          pathActive
            ? "bg-amber-400/15 text-amber-900 dark:text-amber-200 font-medium"
            : "hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200",
          open && !pathActive && "ring-1 ring-amber-400/40 dark:ring-amber-500/30",
          pillar.comingSoon && "opacity-70",
        )}
        aria-expanded={open}
      >
        {pillar.label}
        <ChevronDown
          className={clsx("w-4 h-4 transition-transform", open && "rotate-180")}
        />
      </button>
    </div>
  )
}

function PillarDropdownMenu({
  pillar,
  position,
  isActive,
  onNavigate,
}: {
  pillar: NavPillar
  position: { left: number; top: number }
  isActive: (href: string) => boolean
  onNavigate: () => void
}) {
  return (
    <div
      className="fixed z-[85] min-w-[11rem] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl overflow-hidden"
      style={{ left: position.left, top: position.top }}
      role="menu"
    >
      {pillar.links.map((link) =>
        pillar.comingSoon || link.href === "#" ? (
          <span
            key={link.label}
            className="block px-4 py-2.5 text-sm text-slate-500 dark:text-slate-500 cursor-not-allowed"
          >
            {link.label}
          </span>
        ) : (
          <Link
            key={link.href}
            href={link.href}
            onClick={onNavigate}
            className={clsx(
              "block px-4 py-2.5 text-sm hover:bg-slate-100 dark:hover:bg-slate-800",
              isActive(link.href)
                ? "text-amber-800 dark:text-amber-300 font-medium"
                : "text-slate-700 dark:text-slate-300",
            )}
          >
            {link.label}
          </Link>
        ),
      )}
    </div>
  )
}

function NavLink({
  href,
  active,
  onClick,
  children,
}: {
  href: string
  active?: boolean
  onClick?: () => void
  children: React.ReactNode
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={clsx(
        "px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap",
        active
          ? "bg-amber-400/15 text-amber-900 dark:text-amber-200 font-medium"
          : "hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200",
      )}
    >
      {children}
    </Link>
  )
}

interface UserMenuProps {
  displayName: string
  email: string
  creditBalance?: number
  accessToken?: string
  emailNeedsVerification?: boolean
  dropdownOpen: boolean
  setDropdownOpen: React.Dispatch<React.SetStateAction<boolean>>
  dropdownRef: React.RefObject<HTMLDivElement | null>
  onLogout: () => void
}

function UserMenu({
  displayName,
  email,
  creditBalance,
  accessToken,
  emailNeedsVerification,
  dropdownOpen,
  setDropdownOpen,
  dropdownRef,
  onLogout,
}: UserMenuProps) {
  const [liveCredits, setLiveCredits] = useState<number | undefined>(creditBalance)
  const fetchedForOpenRef = useRef(false)

  useEffect(() => {
    setLiveCredits(creditBalance)
  }, [creditBalance])

  useEffect(() => {
    if (!dropdownOpen) {
      fetchedForOpenRef.current = false
      return
    }
    if (!accessToken || fetchedForOpenRef.current) return
    fetchedForOpenRef.current = true

    let cancelled = false
    void fetchMe(accessToken)
      .then((user) => {
        if (!cancelled) setLiveCredits(user.credit_balance)
      })
      .catch(() => {
        if (!cancelled) setLiveCredits(creditBalance)
      })

    return () => {
      cancelled = true
    }
  }, [dropdownOpen, accessToken, creditBalance])

  const initials = displayName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setDropdownOpen((v) => !v)}
        className="flex items-center gap-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg px-2 py-1.5 transition-colors"
        aria-haspopup="true"
        aria-expanded={dropdownOpen}
      >
        <div className="w-7 h-7 rounded-full bg-amber-500/20 dark:bg-amber-400/20 border border-amber-500/40 dark:border-amber-400/30 flex items-center justify-center text-amber-700 dark:text-amber-400 text-xs font-semibold">
          {initials}
        </div>
        <span className="text-sm text-slate-800 dark:text-slate-200 max-w-[120px] truncate hidden sm:block">
          {displayName}
        </span>
        <ChevronDown
          className={clsx(
            "w-4 h-4 text-slate-600 dark:text-slate-400 transition-transform hidden sm:block",
            dropdownOpen && "rotate-180",
          )}
        />
      </button>

      {dropdownOpen && (
        <div
          className="absolute right-0 mt-2 w-56 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl overflow-hidden z-[100]"
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800">
            <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">{displayName}</p>
            <p className="text-xs text-slate-600 dark:text-slate-400 truncate">{email}</p>
            {emailNeedsVerification && (
              <p className="text-xs text-amber-800 dark:text-amber-300 mt-1">
                Email not verified —{" "}
                <Link
                  href="/settings#email-verification"
                  onClick={() => setDropdownOpen(false)}
                  className="font-medium underline underline-offset-2"
                >
                  verify in Settings
                </Link>
              </p>
            )}
            {liveCredits !== undefined && (
              <p className="text-xs text-amber-700 dark:text-amber-400 mt-0.5">
                {liveCredits} credit{liveCredits !== 1 ? "s" : ""} remaining
              </p>
            )}
          </div>

          <div className="p-1">
            <DropdownItem
              href="/dashboard"
              icon={<LayoutDashboard className="w-4 h-4" />}
              onNavigate={() => setDropdownOpen(false)}
            >
              Dashboard
            </DropdownItem>
            <DropdownItem
              href="/profile"
              icon={<UserCircle className="w-4 h-4" />}
              onNavigate={() => setDropdownOpen(false)}
            >
              Master resume
            </DropdownItem>
            <DropdownItem
              href="/settings"
              icon={<Settings className="w-4 h-4" />}
              onNavigate={() => setDropdownOpen(false)}
            >
              Settings
            </DropdownItem>
            <DropdownItem
              href="/billing"
              icon={<CreditCard className="w-4 h-4" />}
              onNavigate={() => setDropdownOpen(false)}
            >
              Billing
            </DropdownItem>
            <DropdownItem
              href="/settings#help-feedback"
              icon={<LifeBuoy className="w-4 h-4" />}
              onNavigate={() => setDropdownOpen(false)}
            >
              Help &amp; report a bug
            </DropdownItem>
            <DropdownItem
              href="/settings#tutorial-tips"
              icon={<GraduationCap className="w-4 h-4" />}
              onNavigate={() => setDropdownOpen(false)}
            >
              Tutorial tips
            </DropdownItem>
          </div>

          <div className="p-1 border-t border-slate-200 dark:border-slate-800">
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => void onLogout()}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-red-700 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function DropdownItem({
  href,
  icon,
  children,
  onNavigate,
}: {
  href: string
  icon: React.ReactNode
  children: React.ReactNode
  onNavigate?: () => void
}) {
  return (
    <Link
      href={href}
      onClick={() => onNavigate?.()}
      className="flex items-center gap-2.5 px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
    >
      <span className="text-slate-600 dark:text-slate-400">{icon}</span>
      {children}
    </Link>
  )
}
