-- Warehouse tables (filled by data/seed/generate.py)

CREATE TABLE analytics.regions (
    region_id   INT PRIMARY KEY,
    name        TEXT NOT NULL,
    country     TEXT NOT NULL
);

CREATE TABLE analytics.customers (
    customer_id INT PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    email       TEXT NOT NULL,           -- PII
    region_id   INT REFERENCES analytics.regions (region_id),  -- NULL for ~2% (ISSUE-003)
    segment     TEXT NOT NULL,           -- consumer | small_business | enterprise
    signup_date DATE NOT NULL
);

CREATE TABLE analytics.products (
    product_id  INT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    price       NUMERIC(10, 2) NOT NULL,
    is_active   BOOLEAN NOT NULL
);

CREATE TABLE analytics.orders (
    order_id    INT PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES analytics.customers (customer_id),
    order_date  DATE NOT NULL,
    status      TEXT NOT NULL,           -- placed | shipped | completed | returned | cancelled
    channel     TEXT,                    -- web | mobile_app | marketplace | store; NULL before 2023-03-01 (ISSUE-001)
    amount      NUMERIC(12, 2) NOT NULL  -- sum of order_items quantity * unit_price
);

CREATE TABLE analytics.order_items (
    order_item_id INT PRIMARY KEY,
    order_id      INT NOT NULL REFERENCES analytics.orders (order_id),
    product_id    INT NOT NULL REFERENCES analytics.products (product_id),
    quantity      INT NOT NULL,
    unit_price    NUMERIC(10, 2) NOT NULL
);

CREATE TABLE analytics.payments (
    payment_id  INT PRIMARY KEY,
    order_id    INT NOT NULL REFERENCES analytics.orders (order_id),
    method      TEXT NOT NULL,           -- credit_card | debit_card | paypal | gift_card | bank_transfer
    amount      NUMERIC(12, 2) NOT NULL,
    paid_at     TIMESTAMP NOT NULL
);

CREATE TABLE analytics.refunds (
    refund_id   INT PRIMARY KEY,
    order_id    INT NOT NULL REFERENCES analytics.orders (order_id),
    amount      NUMERIC(12, 2) NOT NULL,
    refunded_at DATE NOT NULL,
    reason      TEXT                     -- NULL before 2024-01-01 (ISSUE-002)
);

-- Deprecated: kept for a trap in the eval set. Do not use.
CREATE TABLE analytics.legacy_orders_v1 (
    id          INT PRIMARY KEY,
    cust        INT,
    dt          DATE,
    total       NUMERIC(12, 2)
);

-- RAG index (filled by ingestion/ingest_docs.py)
CREATE TABLE knowledge.chunks (
    chunk_id     TEXT PRIMARY KEY,       -- e.g. table:analytics.orders, metric:net_revenue
    source_type  TEXT NOT NULL,          -- table | metric | issue | glossary
    source_path  TEXT NOT NULL,
    title        TEXT NOT NULL,
    content      TEXT NOT NULL,
    table_names  TEXT[] NOT NULL DEFAULT '{}',
    metadata     JSONB NOT NULL DEFAULT '{}',
    content_hash TEXT NOT NULL,
    embedding    vector(384) NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX chunks_embedding_hnsw ON knowledge.chunks
    USING hnsw (embedding vector_cosine_ops);
