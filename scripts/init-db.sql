-- VNA Database Initialization
-- Creates all databases on first PostgreSQL start
-- POSTGRES_USER is injected by the Docker entrypoint

DO $$
BEGIN
    CREATE DATABASE vna_main;
    CREATE DATABASE bidsserver;
    CREATE DATABASE orthanc;
EXCEPTION WHEN duplicate_database THEN NULL;
END
$$;

DO $$
BEGIN
    PERFORM d.datname FROM pg_database d WHERE d.datname = 'vna_main';
    EXECUTE format('GRANT ALL PRIVILEGES ON DATABASE vna_main TO %I', current_user);
    PERFORM d.datname FROM pg_database d WHERE d.datname = 'bidsserver';
    EXECUTE format('GRANT ALL PRIVILEGES ON DATABASE bidsserver TO %I', current_user);
    PERFORM d.datname FROM pg_database d WHERE d.datname = 'orthanc';
    EXECUTE format('GRANT ALL PRIVILEGES ON DATABASE orthanc TO %I', current_user);
END
$$;
