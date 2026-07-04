import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { routeFromHash, useHashRoute } from "@/lib/useHashRoute"

describe("routeFromHash", () => {
  it("maps known hashes to routes and defaults unknown ones to the console", () => {
    expect(routeFromHash("")).toBe("console")
    expect(routeFromHash("#/")).toBe("console")
    expect(routeFromHash("#/evidence")).toBe("evidence")
    expect(routeFromHash("#/insights")).toBe("insights")
    expect(routeFromHash("#/overview")).toBe("overview")
    expect(routeFromHash("#/bogus")).toBe("console")
  })
})

describe("useHashRoute", () => {
  beforeEach(() => {
    window.location.hash = ""
  })
  afterEach(() => {
    window.location.hash = ""
  })

  it("starts from the current hash", () => {
    window.location.hash = "#/evidence"
    const { result } = renderHook(() => useHashRoute())
    expect(result.current.route).toBe("evidence")
  })

  it("navigate() updates the hash and the reported route", () => {
    const { result } = renderHook(() => useHashRoute())
    expect(result.current.route).toBe("console")

    act(() => result.current.navigate("overview"))
    expect(window.location.hash).toBe("#/overview")
    expect(result.current.route).toBe("overview")
  })

  it("reacts to external hashchange (e.g. browser back button)", () => {
    const { result } = renderHook(() => useHashRoute())
    // Simulate a browser back/forward: the URL changes and a hashchange fires.
    // (jsdom doesn't auto-dispatch hashchange on a programmatic hash set.)
    act(() => {
      window.location.hash = "#/evidence"
      window.dispatchEvent(new Event("hashchange"))
    })
    expect(result.current.route).toBe("evidence")
  })

  it("navigating to the route it's already on keeps that route (idempotent redirect)", () => {
    const { result } = renderHook(() => useHashRoute())
    act(() => result.current.navigate("console"))
    expect(result.current.route).toBe("console")
  })

  it("navigate('insights') updates the hash and the reported route", () => {
    const { result } = renderHook(() => useHashRoute())
    act(() => result.current.navigate("insights"))
    expect(window.location.hash).toBe("#/insights")
    expect(result.current.route).toBe("insights")
  })
})
