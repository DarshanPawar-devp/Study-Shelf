-- StudyShelf migration 001: student accounts, notifications, uploader, login tracking
-- Run ONCE in Supabase > SQL Editor. It only ADDS things; it deletes nothing.
-- Rollback: migrations/001_rollback.sql

-- 1. admins: a permanent id (usernames can be renamed) + optional friendly name
ALTER TABLE admins ADD COLUMN id BIGINT GENERATED ALWAYS AS IDENTITY;
ALTER TABLE admins ADD CONSTRAINT admins_id_key UNIQUE (id);
ALTER TABLE admins ADD COLUMN display_name TEXT;

-- 2. notes: who uploaded it (old notes stay NULL = "Uploader unknown")
ALTER TABLE notes ADD COLUMN uploaded_by BIGINT REFERENCES admins(id) ON DELETE SET NULL;

-- 3. profiles: one row per student, same id as Supabase Auth.
--    Email and password stay in Supabase Auth only.
CREATE TABLE profiles (
  id             UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name      TEXT NOT NULL CHECK (char_length(full_name) BETWEEN 1 AND 80),
  course         TEXT REFERENCES courses(code) ON UPDATE CASCADE ON DELETE SET NULL,
  year           TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_active_at TIMESTAMPTZ
);
CREATE INDEX profiles_course_idx      ON profiles (course);
CREATE INDEX profiles_created_idx     ON profiles (created_at);
CREATE INDEX profiles_last_active_idx ON profiles (last_active_at);

-- 4. notifications: one row per student per note (UNIQUE blocks duplicates)
CREATE TABLE notifications (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id    UUID    NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  note_id    INTEGER NOT NULL REFERENCES notes(id)    ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  read_at    TIMESTAMPTZ,
  UNIQUE (user_id, note_id)
);
CREATE INDEX notifications_user_idx   ON notifications (user_id, created_at DESC);
CREATE INDEX notifications_unread_idx ON notifications (user_id) WHERE read_at IS NULL;

-- 5. login_events: one row per successful student password login
CREATE TABLE login_events (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id    UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX login_events_created_idx ON login_events (created_at);
CREATE INDEX login_events_user_idx    ON login_events (user_id, created_at);

-- 6. Row Level Security: students can only READ their own rows through Supabase's API.
--    No insert/update/delete policies: all writes go through the Flask server.
ALTER TABLE profiles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE login_events  ENABLE ROW LEVEL SECURITY;
CREATE POLICY "read own profile" ON profiles
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = id);
CREATE POLICY "read own notifications" ON notifications
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
