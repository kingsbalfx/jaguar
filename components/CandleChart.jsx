// components/CandleChart.jsx
import React, { useEffect, useRef, useState } from "react";
import { createChart } from "lightweight-charts";

/**
 * CandleChart
 *
 * New features:
 *  - If autoFetch=true and no candles prop is provided, will fetch historical candles
 *    from Binance public REST klines endpoint (start: Sept 1 of current year -> today).
 *  - Pages through Binance results if >1000 candles are needed.
 *  - Optionally subscribes to Binance websocket kline stream for live updates.
 *
 * Props:
 *  - candles: optional array of { time, open, high, low, close } (string 'YYYY-MM-DD' or seconds)
 *  - symbol: e.g. 'BTCUSDT' (default)
 *  - interval: Binance interval string e.g. '1d', '1h', '15m' (default '1d')
 *  - width, height, options (same as before)
 *  - autoFetch: boolean (default true) - fetch from Binance when candles prop absent
 *  - live: boolean (default true) - subscribe to websocket updates (Binance)
 *
 * Notes:
 *  - Binance REST klines endpoint: GET /api/v3/klines (public). No API key required for public market data.
 *    Docs: https://developers.binance.com/docs/spot#kline-candlestick-data. :contentReference[oaicite:2]{index=2}
 *  - Binance websocket kline stream: <symbol>@kline_<interval> (wss://stream.binance.com:9443/ws/...). :contentReference[oaicite:3]{index=3}
 *  - lightweight-charts timeScale.setVisibleRange clamps to available data; it cannot extrapolate missing points. To guarantee empty space you must add dummy points or use logical ranges. :contentReference[oaicite:4]{index=4}
 */

const BINANCE_REST = "https://api.binance.com/api/v3/klines";
const BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws";

const INTERVAL_MS = {
  "1m": 60 * 1000,
  "3m": 3 * 60 * 1000,
  "5m": 5 * 60 * 1000,
  "15m": 15 * 60 * 1000,
  "30m": 30 * 60 * 1000,
  "1h": 60 * 60 * 1000,
  "2h": 2 * 60 * 60 * 1000,
  "4h": 4 * 60 * 60 * 1000,
  "6h": 6 * 60 * 60 * 1000,
  "8h": 8 * 60 * 60 * 1000,
  "12h": 12 * 60 * 60 * 1000,
  "1d": 24 * 60 * 60 * 1000,
  "3d": 3 * 24 * 60 * 60 * 1000,
  "1w": 7 * 24 * 60 * 60 * 1000,
};

export default function CandleChart({
  candles = null,
  symbol = "BTCUSDT",
  interval = "1d",
  autoFetch = true,
  live = true,
  width = "100%",
  height = 360,
  options = {},
}) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const wsRef = useRef(null);
  const [isLoading, setIsLoading] = useState(false);

  // normalize time to 'YYYY-MM-DD' or seconds number for lightweight-charts
  const normalizeTime = (t) => {
    if (typeof t === "number") {
      if (t > 1e12) return Math.floor(t / 1000); // ms -> seconds
      return t;
    }
    if (typeof t === "string") {
      const isoDateLike = /^\d{4}-\d{2}-\d{2}/.test(t);
      if (isoDateLike) return t;
      const ms = new Date(t).valueOf();
      if (!isNaN(ms)) return Math.floor(ms / 1000);
    }
    return Math.floor(Date.now() / 1000);
  };

  const toSeriesData = (list) =>
    (list || []).map((c) => ({
      time: normalizeTime(c.time),
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
    }));

  // Helper: fetch klines from Binance for a range (handles paging)
  async function fetchKlinesRange(symbolParam, intervalParam, startMs, endMs) {
    // Binance limit max 1000 per request (UI Klines may allow 1000). We'll request chunks.
    const limit = 1000;
    const results = [];

    let cursorStart = startMs;
    while (cursorStart < endMs) {
      const params = new URLSearchParams({
        symbol: symbolParam,
        interval: intervalParam,
        startTime: String(cursorStart),
        endTime: String(endMs),
        limit: String(limit),
      });

      const url = `${BINANCE_REST}?${params.toString()}`;
      const res = await fetch(url);
      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        throw new Error(`Binance klines error: ${res.status} ${txt}`);
      }
      const data = await res.json();
      if (!Array.isArray(data) || data.length === 0) break;

      // data rows: [ openTime, open, high, low, close, volume, closeTime, ... ]
      for (const row of data) {
        const [openTime, open, high, low, close] = row;
        results.push({
          time: Math.floor(openTime / 1000),
          open,
          high,
          low,
          close,
        });
      }

      // If less than limit returned, we're done
      if (data.length < limit) break;

      // Advance cursor to last returned openTime + interval
      const lastOpen = data[data.length - 1][0];
      const step = INTERVAL_MS[intervalParam] || INTERVAL_MS["1d"];
      cursorStart = lastOpen + step;
      // safety: avoid infinite loops
      if (results.length > 100000) break;
    }

    return results;
  }

  // open websocket kline stream for live updates
  function startWebsocket(symbolParam, intervalParam) {
    try {
      const wsSymbol = symbolParam.toLowerCase();
      const stream = `${wsSymbol}@kline_${intervalParam}`;
      const wsUrl = `${BINANCE_WS_BASE}/${stream}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          const k = msg.k; // kline payload
          if (!k) return;
          const isFinal = k.x; // whether kline is closed
          const candle = {
            time: Math.floor(k.t / 1000),
            open: k.o,
            high: k.h,
            low: k.l,
            close: k.c,
          };
          if (seriesRef.current) {
            // For a live stream, update the last bar (or append)
            seriesRef.current.update(candle);
            // if final candle closed, consider fetching or updating stored dataset if needed
          }
        } catch (e) {
          // ignore parse errors
        }
      };

      ws.onopen = () => {
        // console.log("Binance WS open", wsUrl);
      };
      ws.onclose = () => {
        // console.log("Binance WS closed");
      };
      ws.onerror = (err) => {
        // console.warn("WS error", err);
      };
    } catch (err) {
      // ignore websocket errors
    }
  }

  // stop websocket
  function stopWebsocket() {
    try {
      if (wsRef.current) {
        try { wsRef.current.close(); } catch (e) {}
        wsRef.current = null;
      }
    } catch (e) {}
  }

  useEffect(() => {
    if (!containerRef.current) return;

    const defaultOptions = {
      width: typeof width === "number" ? width : containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: "solid", color: "#0b1220" },
        textColor: "#d1d5db",
      },
      localization: { dateFormat: "yyyy-MM-dd" },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true },
      grid: { vertLines: { color: "#222" }, horzLines: { color: "#222" } },
      ...options,
    };

    const chart = createChart(containerRef.current, defaultOptions);
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#16a34a",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#16a34a",
      wickDownColor: "#ef4444",
    });
    seriesRef.current = candleSeries;

    // handle resize
    const handleResize = () => {
      try {
        const w = containerRef.current.clientWidth;
        chart.applyOptions({ width: w });
      } catch (e) {}
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      stopWebsocket();
      if (chartRef.current) chartRef.current.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // main data flow: if candles prop provided, use it; otherwise fetch from Binance (autoFetch)
  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!seriesRef.current || !chartRef.current) return;

      // If user passed candles prop, use it
      if (Array.isArray(candles) && candles.length > 0) {
        const data = toSeriesData(candles);
        seriesRef.current.setData(data);
        // set visible range from Sept 1 -> today (seconds)
        try {
          const from = Math.floor(new Date(`${new Date().getFullYear()}-09-01`).getTime() / 1000);
          const to = Math.floor(Date.now() / 1000);
          chartRef.current.timeScale().setVisibleRange({ from, to });
        } catch (e) {}
        return;
      }

      if (!autoFetch) return;

      setIsLoading(true);
      try {
        // compute start: Sept 1 of current year (00:00 UTC)
        const year = new Date().getFullYear();
        const sept1 = new Date(`${year}-09-01T00:00:00Z`).getTime(); // ms
        const nowMs = Date.now();

        // if sept1 is in future (for months before September), fallback to Sept 1 last year
        let startMs = sept1;
        if (startMs > nowMs) {
          startMs = new Date(`${year - 1}-09-01T00:00:00Z`).getTime();
        }

        // fetch with paging
        const fetched = await fetchKlinesRange(symbol, interval, startMs, nowMs);
        if (!mounted) return;

        if (fetched && fetched.length) {
          seriesRef.current.setData(fetched);
          // set visible range from sept1 -> now (in seconds)
          try {
            const fromSec = Math.floor(startMs / 1000);
            const toSec = Math.floor(nowMs / 1000);
            // setVisibleRange will be clamped to available data if necessary.
            chartRef.current.timeScale().setVisibleRange({ from: fromSec, to: toSec });
          } catch (e) {
            // ignore
          }
        }
      } catch (err) {
        // console.error("Failed to fetch klines:", err);
      } finally {
        if (mounted) setIsLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, interval, candles, autoFetch]);

  // websocket subscription for live updates
  useEffect(() => {
    // only start WS if live=true and symbol is provided
    if (!live) return;
    // only try if symbol looks like alphanumeric pair
    if (!symbol || !/^[A-Za-z0-9_]+$/.test(symbol)) return;
    startWebsocket(symbol, interval);
    return () => stopWebsocket();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, interval, live]);

  return (
    <div className="relative">
      <div
        ref={containerRef}
        style={{
          width: typeof width === "number" ? `${width}px` : width,
          height: typeof height === "number" ? `${height}px` : height,
        }}
        className="candle-chart-container"
      />
      {isLoading && (
        <div className="absolute top-2 right-2 bg-black/60 text-white px-2 py-1 rounded text-xs">
          Loading...
        </div>
      )}
    </div>
  );
}
