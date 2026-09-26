-- Ladon's scam graph: reports, transfers between wallets, evidence and scores.

create table if not exists reports (
    id bigint generated always as identity primary key,
    address text not null,
    -- Keyed hash of the reporter's IP, never the IP itself. Used only to de-duplicate and rate limit.
    reporter text not null,
    description text not null default '',
    created_at timestamptz not null default now(),
    unique (address, reporter)
);
create index if not exists reports_address on reports (address);

create table if not exists transfers (
    signature text not null,
    source text not null,
    destination text not null,
    asset text not null,
    amount double precision not null,
    ts bigint not null,
    primary key (signature, source, destination, asset, amount)
);
create index if not exists transfers_source on transfers (source);
create index if not exists transfers_destination on transfers (destination);

create table if not exists evidence (
    address text primary key,
    items jsonb not null,
    updated_at timestamptz not null default now()
);

create table if not exists checked_wallets (
    address text primary key,
    checked_at timestamptz not null default now()
);

-- Scores are recomputed from the tables above; they are stored so other tools can read them directly.
create table if not exists scores (
    address text primary key,
    risk real not null,
    confidence text not null,
    flagged boolean not null,
    reasons jsonb not null,
    cluster_size integer not null,
    reports integer not null,
    updated_at timestamptz not null default now()
);

-- Supabase exposes the public schema through its REST API. Row level security with no policies
-- denies that API entirely; the engine connects as the database owner and is not affected.
alter table reports enable row level security;
alter table transfers enable row level security;
alter table evidence enable row level security;
alter table checked_wallets enable row level security;
alter table scores enable row level security;
