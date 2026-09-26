create table if not exists reports (
    id bigint generated always as identity primary key,
    address text not null,
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

alter table reports enable row level security;
alter table transfers enable row level security;
alter table evidence enable row level security;
alter table checked_wallets enable row level security;
alter table scores enable row level security;
