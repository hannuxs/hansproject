-- =====================================================================
--  Alternatif MANUAL untuk membuat database & user khusus aplikasi.
--  Cara yang disarankan: install.bat (otomatis, password acak).
--
--  Jalankan sebagai admin MariaDB (port 3307), misalnya:
--    mariadb -h 127.0.0.1 -P 3307 -u root -p < deploy\sql\create_database.sql
--  GANTI 'GANTI_PASSWORD_KUAT' dengan password acak yang panjang, lalu tulis
--  password yang sama di DB_PASSWORD pada file .env.
--
--  Aman bila database sudah berisi tabel lain: tidak ada yang dihapus.
--  Semua tabel website memakai awalan hp_.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `hansproject_web`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'hansproject_app'@'localhost' IDENTIFIED BY 'GANTI_PASSWORD_KUAT';
CREATE USER IF NOT EXISTS 'hansproject_app'@'127.0.0.1' IDENTIFIED BY 'GANTI_PASSWORD_KUAT';

-- Hak akses minimum, HANYA untuk database website (bukan root, bukan semua database).
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES, LOCK TABLES
  ON `hansproject_web`.* TO 'hansproject_app'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES, LOCK TABLES
  ON `hansproject_web`.* TO 'hansproject_app'@'127.0.0.1';

FLUSH PRIVILEGES;
