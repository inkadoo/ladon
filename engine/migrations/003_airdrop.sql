create table if not exists airdrop_profiles (
    wallet text primary key,
    referral_code text not null unique,
    streak integer not null default 0,
    last_checkin date,
    created_at timestamptz not null default now()
);

create table if not exists airdrop_events (
    id bigint generated always as identity primary key,
    wallet text not null references airdrop_profiles(wallet),
    kind text not null check (kind in ('join', 'checkin', 'wallet_check', 'referral_inviter', 'referral_invitee', 'verified_report')),
    points integer not null check (points > 0),
    reference text not null,
    created_at timestamptz not null default now(),
    unique (wallet, kind, reference)
);
create index if not exists airdrop_events_wallet on airdrop_events (wallet);
create index if not exists airdrop_events_daily on airdrop_events (wallet, kind, created_at);

create table if not exists airdrop_referrals (
    invitee text primary key references airdrop_profiles(wallet),
    inviter text not null references airdrop_profiles(wallet),
    created_at timestamptz not null default now(),
    check (invitee <> inviter)
);
create index if not exists airdrop_referrals_inviter on airdrop_referrals (inviter);

alter table airdrop_profiles enable row level security;
alter table airdrop_events enable row level security;
alter table airdrop_referrals enable row level security;
