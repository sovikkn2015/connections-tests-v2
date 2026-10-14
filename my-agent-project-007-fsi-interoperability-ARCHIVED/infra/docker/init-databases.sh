#!/bin/bash
# Project 007 — Create per-module PostgreSQL databases on first startup.
# Mounted into postgres container via docker-compose initdb volume.
# The default "fsi007" database is created by POSTGRES_DB env var.

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE fsi007_m1;
    CREATE DATABASE fsi007_m10;
    CREATE DATABASE fsi007_m8;
    GRANT ALL PRIVILEGES ON DATABASE fsi007_m1 TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE fsi007_m10 TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE fsi007_m8 TO $POSTGRES_USER;
EOSQL
