create table if not exists takeovers (
    signature text not null,
    victim text not null,
    attacker text not null,
    token_account text not null,
    ts bigint not null,
    primary key (signature, token_account)
);
create index if not exists takeovers_attacker on takeovers (attacker);

alter table takeovers enable row level security;

alter table reports add column if not exists tx_signature text;
