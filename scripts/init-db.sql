-- Runs once, on first initialisation of an empty Postgres data directory.
--
-- Table creation is intentionally NOT here: Alembic owns the schema so that
-- local SQLite and containerised Postgres stay in sync from one source. This
-- file only prepares database-level extras that migrations should not manage.

-- Case-insensitive / accent-insensitive search on skill names and titles.
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Trigram index support, useful once skill libraries grow large enough that
-- ILIKE '%term%' scans become slow.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- gen_random_uuid(), handy for manual inserts during debugging.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
