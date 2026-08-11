create table if not exists battery_samples (
  id bigserial primary key,
  device_id text not null,
  hostname text,
  os_name text,
  battery_name text,
  status text,
  source text not null default 'battery_collector',
  collected_at timestamptz not null,
  received_at timestamptz not null default now(),
  soc_percent numeric(5, 2),
  designed_capacity_mah integer,
  current_capacity_mah integer,
  full_charge_capacity_mah integer,
  current_ma integer,
  voltage_mv integer,
  power_mw integer,
  cycle_count integer,
  temperature_c numeric(5, 2),
  health_percent numeric(5, 2),
  extra jsonb not null default '{}'::jsonb
);

create index if not exists battery_samples_device_collected_at_idx
  on battery_samples (device_id, collected_at desc);

