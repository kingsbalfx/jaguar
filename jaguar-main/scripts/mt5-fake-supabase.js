/**
 * Minimal in-memory stand-in for the Supabase JS client, scoped to exactly the
 * query surface services/mt5Sync.js uses:
 *   from(table).select(...).eq/in/order/limit/range/.maybeSingle()
 *   from(table).insert([...]).select("id").maybeSingle()
 *   from(table).upsert([...], { onConflict }).eq(...)
 *   from(table).update({...}).eq(...)
 *   from(table).delete().eq(...)/.in(...)
 *
 * Used by scripts/verify-mt5-sync.js so the sync service can be exercised end to
 * end (trades -> analytics -> cursor -> audit) with zero network access.
 */

function clone(value) {
  return value === null || value === undefined ? value : JSON.parse(JSON.stringify(value));
}

function matchesFilters(row, filters = []) {
  return filters.every(({ op, column, value }) => {
    if (op === "eq") return row?.[column] === value;
    if (op === "in") return Array.isArray(value) && value.includes(row?.[column]);
    if (op === "notNull") return row?.[column] !== null && row?.[column] !== undefined;
    return true;
  });
}

function applyOrder(rows, order) {
  if (!order) return rows;
  const { column, ascending = true, nullsFirst = false } = order;
  return [...rows].sort((left, right) => {
    const a = left?.[column];
    const b = right?.[column];
    if (a === b) return 0;
    if (a === null || a === undefined) return nullsFirst ? -1 : 1;
    if (b === null || b === undefined) return nullsFirst ? 1 : -1;
    if (a > b) return ascending ? 1 : -1;
    return ascending ? -1 : 1;
  });
}

/** Mirror PostgREST column projection so select("a,b") really hides other columns. */
function projectColumns(rows, columns) {
  if (!columns || columns === "*" || String(columns).includes("*")) return rows;
  const keys = String(columns)
    .split(",")
    .map((key) => key.trim())
    .filter(Boolean);
  return rows.map((row) => {
    const projected = {};
    for (const key of keys) {
      if (row && Object.prototype.hasOwnProperty.call(row, key)) projected[key] = row[key];
    }
    return projected;
  });
}

class FakeQuery {
  constructor(client, table) {
    this.client = client;
    this.table = table;
    this.state = {
      action: "select",
      columns: "*",
      count: null,
      head: false,
      filters: [],
      order: null,
      limit: null,
      range: null,
      payload: null,
      onConflict: null,
    };
  }

  select(columns = "*", options = {}) {
    if (this.state.action === "select") {
      this.state.columns = columns;
      this.state.count = options.count || null;
      this.state.head = Boolean(options.head);
    }
    return this;
  }

  insert(payload) {
    this.state.action = "insert";
    this.state.payload = Array.isArray(payload) ? payload : [payload];
    return this;
  }

  upsert(payload, options = {}) {
    this.state.action = "upsert";
    this.state.payload = Array.isArray(payload) ? payload : [payload];
    this.state.onConflict = options.onConflict || null;
    return this;
  }

  update(payload) {
    this.state.action = "update";
    this.state.payload = payload;
    return this;
  }

  delete() {
    this.state.action = "delete";
    return this;
  }

  eq(column, value) {
    this.state.filters.push({ op: "eq", column, value });
    return this;
  }

  in(column, value) {
    this.state.filters.push({ op: "in", column, value });
    return this;
  }

  not(column, operator, value) {
    if (String(operator).toLowerCase() === "is" && value === null) {
      this.state.filters.push({ op: "notNull", column });
    }
    return this;
  }

  order(column, options = {}) {
    this.state.order = {
      column,
      ascending: options.ascending !== false,
      nullsFirst: Boolean(options.nullsFirst),
    };
    return this;
  }

  limit(value) {
    this.state.limit = value;
    return this;
  }

  range(from, to) {
    this.state.range = [from, to];
    return this;
  }

  maybeSingle() {
    return this.execute(true);
  }

  single() {
    return this.execute(true);
  }

  then(resolve, reject) {
    return this.execute(false).then(resolve, reject);
  }

  async execute(single) {
    const { table } = this;
    if (this.client.failTables.has(table)) {
      return {
        data: null,
        count: null,
        error: { code: "42P01", message: `relation "public.${table}" does not exist` },
      };
    }
    if (!this.client.tables[table]) this.client.tables[table] = [];
    const rows = this.client.tables[table];
    const state = this.state;
    const filter = (row) => matchesFilters(row, state.filters);

    if (state.action === "insert" || state.action === "upsert") {
      const written = [];
      for (const item of state.payload || []) {
        const record = clone(item);
        if (!record.id) record.id = `${table}-${this.client.sequence++}`;
        if (state.action === "upsert") {
          const keys = String(state.onConflict || "id")
            .split(",")
            .map((key) => key.trim())
            .filter(Boolean);
          const index = rows.findIndex((row) => keys.every((key) => row?.[key] === record?.[key]));
          if (index >= 0) {
            rows[index] = { ...rows[index], ...record };
            written.push(clone(rows[index]));
            continue;
          }
        }
        rows.push(record);
        written.push(clone(record));
      }
      return { data: single ? written[0] || null : written, count: written.length, error: null };
    }

    const matched = rows.filter(filter);

    if (state.action === "update") {
      const updated = [];
      for (const row of matched) {
        Object.assign(row, clone(state.payload));
        updated.push(clone(row));
      }
      return { data: single ? updated[0] || null : updated, count: updated.length, error: null };
    }

    if (state.action === "delete") {
      const removed = matched.map(clone);
      this.client.tables[table] = rows.filter((row) => !filter(row));
      return { data: single ? removed[0] || null : removed, count: removed.length, error: null };
    }

    let selected = applyOrder(matched, state.order);
    if (state.range) selected = selected.slice(state.range[0], state.range[1] + 1);
    if (state.limit !== null && state.limit !== undefined) selected = selected.slice(0, state.limit);
    selected = selected.map(clone);

    if (state.head) {
      return { data: null, count: selected.length, error: null };
    }
    return {
      data: single ? selected[0] || null : projectColumns(selected, state.columns),
      count: state.count ? selected.length : null,
      error: null,
    };
  }
}

/** Create a fake admin client seeded with table rows. */
export function createFakeSupabase(seed = {}) {
  const client = {
    tables: {},
    sequence: 1,
    failTables: new Set(),
    from(table) {
      return new FakeQuery(client, table);
    },
    rows(table) {
      return client.tables[table] || [];
    },
  };
  for (const [table, rows] of Object.entries(seed)) {
    client.tables[table] = (rows || []).map(clone);
  }
  return client;
}

export { createFakeSupabase as default };

