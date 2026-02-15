# 🔤 SQL COMMANDS EXPLAINED (For Beginners)

**Don't understand the SQL code? This explains every single command!**

---

## What is SQL?

SQL (Structured Query Language) is a language you use to talk to databases.

Think of it like:
- **English**: "Tell me everyone's email address"
- **SQL**: `SELECT email FROM profiles;`

The computer understands SQL and does what you ask!

---

## Basic Commands (You Only Need These 6)

### 1️⃣ CREATE TABLE

**What it does:** Makes a new table (like a spreadsheet)

```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY,
  email VARCHAR(254)
);
```

**Translation:**
```
"Create a table called 'profiles'
  with columns: id (unique identifier) and email (text up to 254 letters)"
```

**Real world:**
```
Like making a new spreadsheet with columns for:
- Column A: ID (unique number)
- Column B: Email (user's email)
```

---

### 2️⃣ CREATE INDEX

**What it does:** Makes lookups faster (like a bookmark)

```sql
CREATE INDEX idx_profiles_email ON profiles(email);
```

**Translation:**
```
"Create an index (bookmark) called idx_profiles_email
  on the profiles table
  so we can quickly find rows by email"
```

**Real world:**
```
Like putting a bookmark on the "Email" column
so when you search for "john@gmail.com"
it finds it super fast instead of reading every row
```

---

### 3️⃣ ALTER TABLE

**What it does:** Changes a table (adds safety features)

```sql
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
```

**Translation:**
```
"Change the profiles table
  to enable Row Level Security
  (each user only sees their own row)"
```

**Real world:**
```
Like putting a lock on the filing cabinet
so John can only see John's folder
and Sarah can only see Sarah's folder
```

---

### 4️⃣ CREATE POLICY

**What it does:** Makes a security rule (who can see what)

```sql
CREATE POLICY "users_read_own_profile" ON profiles
  FOR SELECT USING (auth.uid() = id);
```

**Translation:**
```
"Create a security rule called 'users_read_own_profile'
  on the profiles table
  that allows SELECT (reading)
  only if the logged-in user's ID matches the row's ID"
```

**Real world:**
```
Rule: John can only read rows where id = John's-ID
      Sarah can only read rows where id = Sarah's-ID
      Admin can read all rows (different rule)
```

---

### 5️⃣ INSERT

**What it does:** Adds new data to a table

```sql
INSERT INTO profiles (id, email, name)
VALUES ('123', 'john@gmail.com', 'John');
```

**Translation:**
```
"Insert into the profiles table
  new values:
  id = 123
  email = john@gmail.com
  name = John"
```

**Real world:**
```
Like filling out a form and writing down:
- ID: 123
- Email: john@gmail.com
- Name: John
Then clicking "Save"
```

---

### 6️⃣ SELECT

**What it does:** Reads data from a table

```sql
SELECT * FROM profiles;
```

**Translation:**
```
"Select all columns (*) 
  from the profiles table"
```

**Real world:**
```
Like opening a filing cabinet and saying
"Show me everything in the profiles folder"
```

---

## Key Concepts

### Columns (Vertical)

```
ID      EMAIL                  NAME
────────────────────────────────────────
123     john@gmail.com         John
456     sarah@example.com      Sarah
789     mike@test.com          Mike
```

**Columns are the VERTICAL lines.**
- id column (all the IDs)
- email column (all the emails)
- name column (all the names)

### Rows (Horizontal)

```
ID      EMAIL                  NAME
────────────────────────────────────────
123     john@gmail.com         John      ← ROW 1
456     sarah@example.com      Sarah     ← ROW 2
789     mike@test.com          Mike      ← ROW 3
```

**Rows are the HORIZONTAL lines.**
- Row 1: John's data
- Row 2: Sarah's data
- Row 3: Mike's data

---

## Data Types (What Kind of Data?)

### VARCHAR(254)
**Text** up to 254 characters
```
Examples: 'john@gmail.com', 'Sarah', 'Hello World'
```

### UUID
**Unique ID** - a special number that's never the same twice
```
Examples: '550e8400-e29b-41d4-a716-446655440000'
```

### BOOLEAN
**True or False** (yes or no)
```
Examples: true, false
```

### TIMESTAMP
**Date and time** (when something happened)
```
Examples: '2026-02-10 14:30:00', now()
```

### JSONB
**Special data** (complicated info in JSON format)
```
Examples: '{"status":"success","amount":1000}'
```

### BIGINT
**Big number** (for amounts of money)
```
Examples: 100000 (meaning $1000 in cents), 50
```

---

## Common Patterns

### Pattern 1: Create a table with multiple columns

```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY,          ← Unique ID
  email VARCHAR(254),           ← Email address
  name VARCHAR(255),            ← Person's name
  created_at TIMESTAMP          ← When created
);
```

**What it does:**
Creates a table with 4 columns, each with different data types

---

### Pattern 2: Add a speed boost

```sql
CREATE INDEX idx_profiles_email ON profiles(email);
```

**What it does:**
Makes searches by email super fast

---

### Pattern 3: Protect the data

```sql
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_can_read_own" ON profiles
  FOR SELECT USING (auth.uid() = id);
```

**What it does:**
- Turns on security
- Makes rule: users can only see their own row

---

### Pattern 4: Add test data

```sql
INSERT INTO profiles (id, email, name)
VALUES ('550e8400-e29b-41d4-a716-446655440000', 'john@gmail.com', 'John');
```

**What it does:**
Adds a new user to the profiles table

---

### Pattern 5: Read the data

```sql
SELECT * FROM profiles;
```

**What it does:**
Shows all data in the profiles table

---

## Understanding Comments

In SQL, `--` makes a comment (the code ignores it)

```sql
-- This is a comment, computer ignores this line
CREATE TABLE profiles (  -- This creates a table
  id UUID PRIMARY KEY    -- Unique ID column
);                       -- End of table definition
```

**Comments are just notes for humans!**

It's like:
```
Normal sentence: John is 25 years old
With comment:    John is 25 years old  -- He was born in 2001
```

The comment explains it, but the computer ignores it.

---

## READING THE CODE YOU COPY

### Example: profiles table

```sql
CREATE TABLE IF NOT EXISTS profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email VARCHAR(254) UNIQUE NOT NULL,
  name VARCHAR(255),
  role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'vip', 'premium')),
  lifetime BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Breaking it down:**

```
CREATE TABLE IF NOT EXISTS profiles (
├── CREATE TABLE: Make new table called "profiles"
├── IF NOT EXISTS: Only if it doesn't already exist
│
├── id UUID PRIMARY KEY REFERENCES...
│   └─ Column: "id" (unique ID) that points to auth.users table
│
├── email VARCHAR(254) UNIQUE NOT NULL
│   ├─ Column: "email" (text, max 254 chars)
│   ├─ UNIQUE: Can't have two people with same email
│   └─ NOT NULL: Must have a value (can't be empty)
│
├── name VARCHAR(255)
│   └─ Column: "name" (text, max 255 chars) - optional
│
├── role VARCHAR(50) DEFAULT 'user' CHECK (...)
│   ├─ Column: "role" (text)
│   ├─ DEFAULT 'user': If not given, use 'user'
│   └─ CHECK: Must be one of: admin, user, vip, premium
│
├── lifetime BOOLEAN DEFAULT FALSE
│   ├─ Column: "lifetime" (true/false)
│   └─ DEFAULT FALSE: If not given, use false
│
├── created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
│   ├─ Column: "created_at" (date & time)
│   └─ DEFAULT CURRENT_TIMESTAMP: Use current time if not given
│
└── updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    └─ Same as above
);
```

---

## KEYWORDS YOU'LL SEE

| Keyword | Means |
|---------|-------|
| **CREATE** | Make something new |
| **TABLE** | A table (spreadsheet) |
| **IF NOT EXISTS** | Only if it doesn't already exist |
| **PRIMARY KEY** | Unique identifier (no two can be same) |
| **VARCHAR(X)** | Text (max X characters) |
| **UUID** | Special unique ID |
| **UNIQUE** | Can't have duplicates |
| **NOT NULL** | Can't be empty |
| **DEFAULT** | Use this value if not given |
| **BOOLEAN** | True or False |
| **TIMESTAMP** | Date and time |
| **CURRENT_TIMESTAMP** | Right now |
| **CHECK** | Must match this condition |
| **ALTER** | Change something |
| **ENABLE** | Turn on |
| **ROW LEVEL SECURITY** | Each user sees only their rows |
| **CREATE POLICY** | Make a security rule |
| **FOR** | This rule applies to... |
| **SELECT** | Reading data |
| **USING** | Only if this is true |
| **INSERT** | Add new data |
| **VALUES** | The data to add |
| **REFERENCES** | Points to another table |
| **FOREIGN KEY** | Links to another table |
| **JSONB** | Complicated data format |
| **INDEX** | Speed boost for lookups |

---

## PUTTING IT ALL TOGETHER

When you copy the SQL code, you're basically saying:

```
Computer, please:

1. Create 4 tables (profiles, payments, subscriptions, bot_logs)
2. Each table with the right columns
3. Add some speed boosts (indexes)
4. Add security (RLS policies)
5. Make sure users only see their own rows
6. Make sure only the backend can see payments/logs
7. Done!
```

That's it! The code does all this automatically.

---

## WHY SQL LOOKS COMPLICATED

It's not complicated, it's just:
- **Verbose**: Writes out everything clearly
- **Specific**: Must be exact
- **Powerful**: Can do complex things

Think of it like:
```
Regular talking: "Make a table for users"
SQL: "CREATE TABLE IF NOT EXISTS users (
      id UUID PRIMARY KEY,
      email VARCHAR(254) UNIQUE NOT NULL
    );"
```

SQL is just more detailed!

---

## QUICK REFERENCE

### Make a table:
```sql
CREATE TABLE table_name (
  column_name DATA_TYPE
);
```

### Make it faster:
```sql
CREATE INDEX index_name ON table_name(column_name);
```

### Protect it:
```sql
ALTER TABLE table_name ENABLE ROW LEVEL SECURITY;
```

### Make a security rule:
```sql
CREATE POLICY "rule_name" ON table_name
  FOR SELECT USING (condition);
```

### Add data:
```sql
INSERT INTO table_name (column1, column2)
VALUES (value1, value2);
```

### Read data:
```sql
SELECT * FROM table_name;
```

---

## YOU DON'T NEED TO MEMORIZE

You don't need to learn all of SQL!

You just need to:
1. ✓ Copy the code I gave you
2. ✓ Paste it into Supabase
3. ✓ Click "Run"
4. ✓ See "Success!" ✅

**The computer does the rest!**

If you're curious, read this file. If you're not, just copy & paste! 👍

---

**Next:** Back to SUPABASE_MASTER_GUIDE.md 👈


