/**
 * Comprehensive Error Handling & Logging
 * Centralized error tracking and structured logging
 */

export class AppError extends Error {
  constructor(message, statusCode = 500, code = "INTERNAL_ERROR") {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.timestamp = new Date().toISOString();
  }
}

export class ValidationError extends AppError {
  constructor(message) {
    super(message, 400, "VALIDATION_ERROR");
  }
}

export class AuthError extends AppError {
  constructor(message = "Unauthorized") {
    super(message, 401, "AUTH_ERROR");
  }
}

export class ForbiddenError extends AppError {
  constructor(message = "Forbidden") {
    super(message, 403, "FORBIDDEN");
  }
}

export class NotFoundError extends AppError {
  constructor(message = "Not found") {
    super(message, 404, "NOT_FOUND");
  }
}

/**
 * Structured Logger
 */
export class Logger {
  static log(level, message, meta = {}) {
    const log = {
      timestamp: new Date().toISOString(),
      level,
      message,
      ...meta,
    };
    console.log(JSON.stringify(log));
    return log;
  }

  static info(message, meta) {
    return this.log("INFO", message, meta);
  }

  static warn(message, meta) {
    return this.log("WARN", message, meta);
  }

  static error(message, error, meta) {
    const errorMeta = {
      error_message: error?.message || String(error),
      error_code: error?.code,
      error_stack: process.env.NODE_ENV === "production" ? undefined : error?.stack,
      ...meta,
    };
    return this.log("ERROR", message, errorMeta);
  }

  static debug(message, meta) {
    if (process.env.NODE_ENV !== "production") {
      return this.log("DEBUG", message, meta);
    }
  }
}

/**
 * Error handler middleware for Express-like handlers
 */
export function withErrorHandling(handler) {
  return async (req, res) => {
    try {
      return await handler(req, res);
    } catch (error) {
      Logger.error("API Error", error, { path: req.url, method: req.method });

      if (error instanceof AppError) {
        return res.status(error.statusCode).json({
          error: error.message,
          code: error.code,
          timestamp: error.timestamp,
        });
      }

      // Generic error
      res.status(500).json({
        error: "Internal Server Error",
        code: "INTERNAL_ERROR",
        timestamp: new Date().toISOString(),
      });
    }
  };
}

/**
 * Request logging middleware
 */
export function logRequest(req, res, next) {
  const start = Date.now();
  const originalEnd = res.end;

  res.end = function (...args) {
    const duration = Date.now() - start;
    Logger.info("HTTP Request", {
      method: req.method,
      path: req.path || req.url,
      status: res.statusCode,
      duration_ms: duration,
      user_id: req.session?.user?.id,
    });
    originalEnd.apply(res, args);
  };

  next && next();
}

/**
 * Global error tracking (for production, integrate with Sentry)
 */
export function captureException(error, context = {}) {
  Logger.error("Exception Captured", error, context);
  // In production: Sentry.captureException(error, { contexts: context });
}
