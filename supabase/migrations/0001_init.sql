-- Confie — schéma initial (PostgreSQL / Supabase)
-- Principe : chaque ligne appartient à une personne, et la sécurité au niveau des lignes (RLS)
-- garantit que personne d'autre ne peut la lire, pas même via la clé publique de l'app.
-- La synchronisation est facultative : sans compte, tout reste sur le téléphone.

create extension if not exists "pgcrypto";

-- ——— Profil et préférences ———
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text check (char_length(display_name) <= 40),
  style text not null default 'douce' check (style in ('douce','franche','positive','ecoute','analyse')),
  frankness smallint not null default 2 check (frankness between 1 and 3),
  default_mode text not null default 'ecoute' check (default_mode in ('ecoute','comprendre','honnete','rassure','solutions','challenge','motive')),
  memory_enabled boolean not null default false,
  consent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ——— Conversations ———
create table public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title text not null default 'Nouvelle conversation' check (char_length(title) <= 80),
  topic text,
  mode text not null default 'ecoute',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index conversations_user_idx on public.conversations (user_id, updated_at desc);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations (id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  role text not null check (role in ('user','assistant')),
  content text not null check (char_length(content) <= 20000),
  via_voice boolean not null default false,
  created_at timestamptz not null default now()
);
create index messages_conversation_idx on public.messages (conversation_id, created_at);

-- ——— Mémoire : « Ce que mon IA retient » ———
create table public.memory_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  content text not null check (char_length(content) between 1 and 240),
  source text not null default 'ia' check (source in ('ia','moi')),
  created_at timestamptz not null default now()
);
create index memory_items_user_idx on public.memory_items (user_id, created_at);

-- ——— Humeur ———
create table public.mood_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  day date not null default current_date,
  mood smallint not null check (mood between 1 and 5),
  emotions text[] not null default '{}',
  intensity smallint check (intensity between 1 and 5),
  stress smallint check (stress between 1 and 5),
  energy smallint check (energy between 1 and 5),
  sleep_hours numeric(3,1) check (sleep_hours between 0 and 24),
  note text check (char_length(note) <= 2000),
  created_at timestamptz not null default now()
);
create index mood_entries_user_idx on public.mood_entries (user_id, day desc);

-- ——— Journal ———
create table public.journal_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  prompt text,
  content text not null check (char_length(content) <= 20000),
  emotions text[] not null default '{}',
  share_with_ai boolean not null default false, -- jamais partagé sans choix explicite
  reflection text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index journal_entries_user_idx on public.journal_entries (user_id, created_at desc);

-- ——— Exercices, objectifs, vidéos gardées ———
create table public.exercise_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  exercise_id text not null,
  helpful boolean,
  created_at timestamptz not null default now()
);
create index exercise_logs_user_idx on public.exercise_logs (user_id, created_at desc);

create table public.goals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  content text not null check (char_length(content) between 1 and 200),
  done_at timestamptz,
  created_at timestamptz not null default now()
);
create index goals_user_idx on public.goals (user_id, created_at);

create table public.saved_videos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  youtube_id text not null,
  title text not null,
  channel text not null,
  why text,
  category text,
  created_at timestamptz not null default now(),
  unique (user_id, youtube_id)
);

-- ——— Compteur d'usage (limites et maîtrise des coûts), écrit uniquement par le serveur ———
create table public.usage_daily (
  user_id uuid not null references auth.users (id) on delete cascade,
  day date not null default current_date,
  messages integer not null default 0,
  primary key (user_id, day)
);

-- ——— Sécurité au niveau des lignes ———
alter table public.profiles enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.memory_items enable row level security;
alter table public.mood_entries enable row level security;
alter table public.journal_entries enable row level security;
alter table public.exercise_logs enable row level security;
alter table public.goals enable row level security;
alter table public.saved_videos enable row level security;
alter table public.usage_daily enable row level security;

create policy "profil : le sien uniquement" on public.profiles
  for all to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

do $$
declare t text;
begin
  foreach t in array array['conversations','messages','memory_items','mood_entries','journal_entries','exercise_logs','goals','saved_videos']
  loop
    execute format(
      'create policy "%1$s : les siennes uniquement" on public.%1$I for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id)', t);
  end loop;
end $$;

-- Un message ne peut être rattaché qu'à une conversation de la même personne.
create policy "messages : conversation à soi" on public.messages
  as restrictive for insert to authenticated
  with check (exists (select 1 from public.conversations c where c.id = conversation_id and c.user_id = (select auth.uid())));

-- L'usage est lisible par la personne, mais seul le serveur (clé de service) peut l'écrire.
create policy "usage : lecture du sien" on public.usage_daily
  for select to authenticated using ((select auth.uid()) = user_id);

-- Aucun accès pour les visiteurs non connectés.
revoke all on all tables in schema public from anon;

-- ——— Création automatique du profil ———
create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id) values (new.id);
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ——— Suppression de toutes ses données (droit à l'effacement) ———
-- Le compte lui-même est supprimé par une fonction serveur (clé de service) : les « on delete cascade » font le reste.
create function public.delete_my_data() returns void
language sql security invoker set search_path = '' as $$
  delete from public.conversations where user_id = (select auth.uid());
  delete from public.memory_items where user_id = (select auth.uid());
  delete from public.mood_entries where user_id = (select auth.uid());
  delete from public.journal_entries where user_id = (select auth.uid());
  delete from public.exercise_logs where user_id = (select auth.uid());
  delete from public.goals where user_id = (select auth.uid());
  delete from public.saved_videos where user_id = (select auth.uid());
$$;
revoke all on function public.delete_my_data() from public, anon;
grant execute on function public.delete_my_data() to authenticated;
