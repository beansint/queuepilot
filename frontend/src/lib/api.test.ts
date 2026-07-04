import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { analyzeTicket, logout } from "@/lib/api"
import { SAMPLE_RESPONSE } from "@/test/fixtures"

describe("analyzeTicket", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("POSTs to /analyze?explain=true with a JSON body and returns the parsed response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => SAMPLE_RESPONSE,
    })
    vi.stubGlobal("fetch", fetchMock)

    const result = await analyzeTicket("My VPN is broken")

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/analyze?explain=true")
    expect(init.method).toBe("POST")
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" })
    expect(JSON.parse(init.body)).toEqual({ text: "My VPN is broken" })
    expect(result).toEqual(SAMPLE_RESPONSE)
  })

  it("throws surfacing `detail` on a non-2xx response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: "text must not be empty" }),
    })
    vi.stubGlobal("fetch", fetchMock)

    await expect(analyzeTicket("   ")).rejects.toThrow("text must not be empty")
  })

  it("falls back to a status message when the error body has no detail", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("not json")
      },
    })
    vi.stubGlobal("fetch", fetchMock)

    await expect(analyzeTicket("boom")).rejects.toThrow("500")
  })
})

describe("logout", () => {
  beforeEach(() => vi.restoreAllMocks())
  afterEach(() => vi.restoreAllMocks())

  it("POSTs to /logout and resolves on success", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 })
    vi.stubGlobal("fetch", fetchMock)

    await expect(logout()).resolves.toBeUndefined()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/logout")
    expect(init.method).toBe("POST")
  })

  it("throws on a non-2xx response so the caller can surface an error", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: "logout failed" }),
    })
    vi.stubGlobal("fetch", fetchMock)

    await expect(logout()).rejects.toThrow("logout failed")
  })
})
