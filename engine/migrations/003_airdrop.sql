create table if not exists airdrop_profiles (
    wallet text primary key,
    referral_code text not null unique,
    streak integer not null default 0,
    last_checkin date,
    created_at timestamptz not null default now()
);
create index if not exists airdrop_profiles_referral_code on airdrop_profiles (referral_code);

create table if not exists airdrop_events (
    id bigint generated always as identity primary key,
    wallet text not null references airdrop_profiles(wallet) on delete cascade,
    kind text not null,
    points integer not null check (points >= 0),
    reference text not null,
    created_at timestamptz not null default now(),
    unique (wallet, kind, reference)
);
create index if not exists airdrop_events_wallet on airdrop_events (wallet);
create index if not exists airdrop_events_created on airdrop_events (created_at);

create table if not exists airdrop_referrals (
    invitee text primary key references airdrop_profiles(wallet) on delete cascade,
    inviter text not null references airdrop_profiles(wallet) on delete cascade,
    created_at timestamptz not null default now(),
    check (invitee <> inviter)
);
create index if not exists airdrop_referrals_inviter on airdrop_referrals (inviter);

alter table airdrop_profiles enable row level security;
alter table airdrop_events enable row level security;
alter table airdrop_referrals enable row level security;
