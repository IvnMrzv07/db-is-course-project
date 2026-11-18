#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --host "$PGHOST" --username "$PGUSER" --dbname cs2_db <<'SQL'
SELECT 'CREATE ROLE ingestion LOGIN PASSWORD ''ingestion-local'''
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname='ingestion')\gexec
SELECT 'CREATE DATABASE ingestion OWNER ingestion'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='ingestion')\gexec
SQL
