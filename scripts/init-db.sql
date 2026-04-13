-- VNA Database Initialization
-- Creates all databases on first PostgreSQL start

CREATE DATABASE vna_main;
CREATE DATABASE bidsserver;
CREATE DATABASE orthanc;

GRANT ALL PRIVILEGES ON DATABASE vna_main TO "vna-admin";
GRANT ALL PRIVILEGES ON DATABASE bidsserver TO "vna-admin";
GRANT ALL PRIVILEGES ON DATABASE orthanc TO "vna-admin";
