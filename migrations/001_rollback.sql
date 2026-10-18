-- Undo migration 001. Only safe BEFORE real student data exists (dropping a table deletes its rows).
DROP TABLE IF EXISTS login_events;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS profiles;
ALTER TABLE notes  DROP COLUMN IF EXISTS uploaded_by;
ALTER TABLE admins DROP COLUMN IF EXISTS display_name;
ALTER TABLE admins DROP CONSTRAINT IF EXISTS admins_id_key;
ALTER TABLE admins DROP COLUMN IF EXISTS id;
