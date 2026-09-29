create table if not exists airdrop_challenges (
    nonce text primary key,
    wallet text not null,
    message text not null,
    expires_at timestamptz not null
);
create table if not exists airdrop_sessions (
    token_hash text primary key,
    wallet text not null,
    expires_at timestamptz not null
);
create index if not exists airdrop_sessions_expiry on airdrop_sessions(expires_at);
create table if not exists airdrop_limits (
    key text not null,
    bucket timestamptz not null,
    count integer not null default 1,
    primary key (key, bucket)
);
create table if not exists airdrop_x_pending (
    state_hash text primary key,
    wallet text not null references airdrop_profiles(wallet),
    session_hash text not null,
    verifier text not null,
    expires_at timestamptz not null
);
create table if not exists airdrop_x_accounts (
    wallet text primary key references airdrop_profiles(wallet),
    user_id text not null unique,
    username text not null,
    access_token text,
    expires_at timestamptz
);
create table if not exists airdrop_quests (
    wallet text not null references airdrop_profiles(wallet),
    task text not null check (task in ('x_connect', 'x_follow', 'x_post')),
    proof text not null,
    created_at timestamptz not null default now(),
    primary key (wallet, task),
    unique (task, proof)
);
alter table airdrop_events drop constraint if exists airdrop_events_kind_check;
alter table airdrop_events add constraint airdrop_events_kind_check check (
    kind in ('join', 'checkin', 'wallet_check', 'referral_inviter', 'referral_invitee', 'verified_report', 'social')
);
alter table airdrop_challenges enable row level security;
alter table airdrop_sessions enable row level security;
alter table airdrop_limits enable row level security;
alter table airdrop_x_pending enable row level security;
alter table airdrop_x_accounts enable row level security;
alter table airdrop_quests enable row level security;
