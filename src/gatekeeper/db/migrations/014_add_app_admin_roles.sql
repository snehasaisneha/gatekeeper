ALTER TABLE apps
ADD COLUMN admin_roles TEXT NOT NULL DEFAULT 'admin';

UPDATE user_app_access
SET is_app_admin = CASE
    WHEN role IS NOT NULL
         AND EXISTS (
             SELECT 1
             FROM apps
             WHERE apps.id = user_app_access.app_id
               AND (
                   ',' || REPLACE(LOWER(apps.admin_roles), ' ', '') || ','
               ) LIKE '%,' || LOWER(user_app_access.role) || ',%'
         )
    THEN 1
    ELSE 0
END;
