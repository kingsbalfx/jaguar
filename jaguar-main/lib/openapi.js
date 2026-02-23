/**
 * API Documentation & OpenAPI Schema
 * 
 * All endpoints for the Jaguar + ICT Trading Bot monorepo
 */

export const openAPISchema = {
  openapi: "3.0.0",
  info: {
    title: "Jaguar Trading Bot API",
    version: "1.0.0",
    description: "Integrated trading bot and mentorship platform",
  },
  servers: [{ url: "https://kingsbalfx.name.ng", description: "Production" }],
  paths: {
    "/health": {
      get: {
        summary: "Health check",
        responses: { 200: { description: "Service is healthy", content: { "application/json": { example: { status: "ok", ts: Date.now() } } } } },
      },
    },
    "/api/korapay/init": {
      post: {
        summary: "Initialize Korapay payment",
        requestBody: { required: true, content: { "application/json": { schema: { $ref: "#/components/schemas/KorapayInit" } } } },
        responses: { 200: { description: "Payment initialized", content: { "application/json": { schema: { $ref: "#/components/schemas/KorapayResponse" } } } } },
      },
    },
    "/api/korapay/webhook": {
      post: {
        summary: "Korapay webhook (payment confirmation)",
        security: [{ KoraSignature: [] }],
        requestBody: { required: true, content: { "application/json": { schema: { $ref: "#/components/schemas/KorapayEvent" } } } },
        responses: { 200: { description: "Event processed" } },
      },
    },
    "/api/korapay/verify": {
      post: {
        summary: "Verify Korapay payment",
        requestBody: { required: true, content: { "application/json": { schema: { $ref: "#/components/schemas/KorapayVerify" } } } },
        responses: { 200: { description: "Payment verified" } },
      },
    },
    "/api/admin/payments": {
      get: {
        summary: "List all payments (admin only)",
        security: [{ AdminKey: [] }],
        responses: { 200: { description: "Payments list", content: { "application/json": { schema: { $ref: "#/components/schemas/PaymentsList" } } } } },
      },
    },
    "/api/admin/users": {
      get: {
        summary: "List all users (admin only)",
        security: [{ SessionAuth: [] }],
        responses: { 200: { description: "Users list", content: { "application/json": { schema: { $ref: "#/components/schemas/UsersList" } } } } },
      },
    },
    "/api/admin/toggle-lifetime": {
      post: {
        summary: "Toggle user lifetime subscription (admin)",
        security: [{ SessionAuth: [] }],
        requestBody: { required: true, content: { "application/json": { schema: { $ref: "#/components/schemas/ToggleLifetime" } } } },
        responses: { 200: { description: "Lifetime toggled" } },
      },
    },
    "/api/admin/bot-logs": {
      get: {
        summary: "Fetch bot activity logs (admin only)",
        security: [{ SessionAuth: [] }],
        parameters: [{ name: "limit", in: "query", schema: { type: "integer", default: 100 } }],
        responses: { 200: { description: "Bot logs", content: { "application/json": { schema: { $ref: "#/components/schemas/BotLogsList" } } } } },
      },
    },
    "/api/analytics/trades": {
      get: {
        summary: "Get trade analytics (win rate, P&L, etc.)",
        security: [{ SessionAuth: [] }],
        responses: { 200: { description: "Trade analytics", content: { "application/json": { schema: { $ref: "#/components/schemas/TradeAnalytics" } } } } },
      },
    },
  },
  components: {
    schemas: {
      Trade: {
        type: "object",
        required: ["symbol", "direction", "entry", "sl", "tp"],
        properties: {
          symbol: { type: "string", example: "EURUSD" },
          direction: { type: "string", enum: ["buy", "sell"] },
          entry: { type: "number", example: 1.0945 },
          sl: { type: "number", example: 1.0920 },
          tp: { type: "number", example: 1.0970 },
          lot: { type: "number", example: 0.1 },
          ml_probability: { type: "number", example: 0.85 },
        },
      },
      KorapayInit: {
        type: "object",
        required: ["email", "amount"],
        properties: { email: { type: "string" }, amount: { type: "integer" } },
      },
      KorapayResponse: { type: "object", properties: { data: { properties: { checkout_url: { type: "string" }, reference: { type: "string" } } } } },
      KorapayEvent: {
        type: "object",
        properties: { event: { type: "string", example: "charge.success" }, data: { type: "object" } },
      },
      KorapayVerify: {
        type: "object",
        required: ["reference"],
        properties: { reference: { type: "string" } },
      },
      PaymentsList: { type: "object", properties: { payments: { type: "array", items: { $ref: "#/components/schemas/Payment" } } } },
      Payment: { type: "object", properties: { id: { type: "string" }, amount: { type: "integer" }, status: { type: "string" }, received_at: { type: "string" } } },
      UsersList: { type: "object", properties: { users: { type: "array", items: { $ref: "#/components/schemas/User" } } } },
      User: { type: "object", properties: { id: { type: "string" }, email: { type: "string" }, role: { type: "string" }, lifetime: { type: "boolean" } } },
      ToggleLifetime: { type: "object", required: ["email", "set"], properties: { email: { type: "string" }, set: { type: "boolean" } } },
      BotLogsList: { type: "object", properties: { logs: { type: "array", items: { $ref: "#/components/schemas/BotLog" } } } },
      BotLog: { type: "object", properties: { event: { type: "string" }, payload: { type: "object" }, created_at: { type: "string" } } },
      TradeAnalytics: {
        type: "object",
        properties: {
          total_trades: { type: "integer" },
          winning_trades: { type: "integer" },
          losing_trades: { type: "integer" },
          win_rate: { type: "number" },
          profit_factor: { type: "number" },
          total_pnl: { type: "number" },
          avg_profit: { type: "number" },
          avg_loss: { type: "number" },
          sharpe_ratio: { type: "number" },
          max_drawdown: { type: "number" },
          by_symbol: { type: "object" },
        },
      },
    },
    securitySchemes: {
      KoraSignature: { type: "apiKey", in: "header", name: "x-korapay-signature" },
      AdminKey: { type: "apiKey", in: "header", name: "x-admin-secret" },
      SessionAuth: { type: "http", scheme: "bearer" },
    },
  },
};

/**
 * Helper to output OpenAPI schema in YAML format for docs
 */
export function getOpenAPIYaml() {
  const yaml = JSON.stringify(openAPISchema, null, 2);
  // In production, use a proper YAML serializer
  return yaml;
}
