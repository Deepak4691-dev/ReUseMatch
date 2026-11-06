CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    account_type TEXT NOT NULL DEFAULT 'individual',   -- individual | organization
    is_admin INTEGER NOT NULL DEFAULT 0,
    lat REAL, lng REAL, area TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    ai_category TEXT,            -- what the classifier suggested (kept to measure accuracy)
    ai_confidence REAL,
    condition TEXT NOT NULL DEFAULT 'good',
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_weight_kg REAL NOT NULL DEFAULT 1,
    lat REAL NOT NULL, lng REAL NOT NULL, address TEXT,
    image TEXT,
    status TEXT NOT NULL DEFAULT 'available',          -- available | reserved | collected
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    collected_at TEXT
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id),
    requester_id INTEGER NOT NULL REFERENCES users(id),
    message TEXT,
    slot TEXT,                                          -- proposed pickup time
    status TEXT NOT NULL DEFAULT 'pending',             -- pending | accepted | declined | cancelled | collected
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS needs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    urgency INTEGER NOT NULL DEFAULT 2,                 -- 1 low, 2 normal, 3 urgent
    min_condition TEXT NOT NULL DEFAULT 'fair',
    status TEXT NOT NULL DEFAULT 'open',                -- open | closed
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
