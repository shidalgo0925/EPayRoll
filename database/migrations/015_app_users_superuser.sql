-- Superusuario de sistema (no eliminable desde la UI)

ALTER TABLE app_users
    ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN NOT NULL DEFAULT false;

UPDATE app_users
SET is_superuser = true, updated_at = now()
WHERE email IN ('shidalgo@eastech.services');
