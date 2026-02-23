/**
 * Unit/Integration Tests for Critical Endpoints
 * Run: npm test or npm run test:unit
 */

import { validateEmail, validateAmount, validateTrade } from "../lib/validation";
import { AppError, ValidationError, AuthError } from "../lib/errors";

describe("Validation Middleware", () => {
  describe("validateEmail", () => {
    test("accepts valid email", () => {
      expect(validateEmail("user@example.com")).toBe(true);
    });

    test("rejects invalid email", () => {
      expect(validateEmail("invalid")).toBe(false);
      expect(validateEmail("")).toBe(false);
      expect(validateEmail(null)).toBe(false);
    });

    test("rejects overly long email", () => {
      const longEmail = "a".repeat(256) + "@example.com";
      expect(validateEmail(longEmail)).toBe(false);
    });
  });

  describe("validateAmount", () => {
    test("accepts valid amount", () => {
      expect(validateAmount(500)).toBe(true);
      expect(validateAmount(500000)).toBe(true);
    });

    test("rejects invalid amount", () => {
      expect(validateAmount(-100)).toBe(false);
      expect(validateAmount(0)).toBe(false);
      expect(validateAmount("invalid")).toBe(false);
      expect(validateAmount(Infinity)).toBe(false);
    });
  });

  describe("validateTrade", () => {
    const validTrade = {
      symbol: "EURUSD",
      direction: "buy",
      entry: 1.0950,
      sl: 1.0920,
      tp: 1.0980,
      lot: 0.1,
    };

    test("accepts valid trade", () => {
      const result = validateTrade(validTrade);
      expect(result.valid).toBe(true);
    });

    test("rejects invalid symbol", () => {
      const result = validateTrade({ ...validTrade, symbol: "INVALID123" });
      expect(result.valid).toBe(false);
      expect(result.error).toContain("symbol");
    });

    test("rejects invalid direction", () => {
      const result = validateTrade({ ...validTrade, direction: "invalid" });
      expect(result.valid).toBe(false);
      expect(result.error).toContain("direction");
    });

    test("rejects invalid prices", () => {
      const result = validateTrade({ ...validTrade, entry: -1 });
      expect(result.valid).toBe(false);
    });
  });
});

describe("Error Classes", () => {
  test("AppError has statusCode and code", () => {
    const error = new AppError("Test error", 400, "TEST_CODE");
    expect(error.statusCode).toBe(400);
    expect(error.code).toBe("TEST_CODE");
    expect(error.message).toBe("Test error");
  });

  test("ValidationError defaults to 400", () => {
    const error = new ValidationError("Bad input");
    expect(error.statusCode).toBe(400);
    expect(error.code).toBe("VALIDATION_ERROR");
  });

  test("AuthError defaults to 401", () => {
    const error = new AuthError();
    expect(error.statusCode).toBe(401);
  });
});

/**
 * API Integration Tests (requires running services)
 * Run with: npm run test:integration
 */

describe("API Integration Tests", () => {
  const BASE_URL = process.env.BASE_URL || "https://kingsbalfx.name.ng";

  test("GET /health returns ok", async () => {
    const res = await fetch(`${BASE_URL}/health`);
    const data = await res.json();
    expect(res.status).toBe(200);
    expect(data.status).toBe("ok");
  });

  test("POST /api/korapay/init requires email and amount", async () => {
    const res = await fetch(`${BASE_URL}/api/korapay/init`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBeGreaterThanOrEqual(400);
  });

  test("GET /api/admin/payments requires admin auth", async () => {
    const res = await fetch(`${BASE_URL}/api/admin/payments`);
    expect(res.status).toBe(401);
  });
});
