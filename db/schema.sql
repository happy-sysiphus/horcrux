-- horcrux 배포용 Supabase 스키마
-- 파일럿 규모라 마이그레이션 도구 없이 Supabase SQL 에디터에서 수동 1회 실행한다.

create table labs (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  invite_code text unique not null,
  created_by uuid not null,
  llm_mode text not null default 'central',   -- 'central' | 'own'
  llm_provider text,                          -- own: 'claude' | 'api'
  llm_credential text,                        -- Fernet 암호문
  daily_llm_limit int not null default 200,
  created_at timestamptz default now()
);
create table lab_members (
  lab_id uuid references labs(id),
  user_id uuid not null,
  role text not null default 'member',        -- 'admin' | 'member'
  primary key (lab_id, user_id)
);
create table llm_usage (
  lab_id uuid references labs(id),
  day date not null,
  count int not null default 0,
  primary key (lab_id, day)
);
