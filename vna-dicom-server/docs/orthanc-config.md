# Orthanc Config Reference

This directory contains the VNA DICOM server's baked-in Orthanc configuration:

- Main config: `../config/orthanc/orthanc.json`
- Lua callback: `../config/orthanc/lua/sync_to_vna.lua`
- Docker build context: `../Dockerfile`

Official Orthanc reference documentation:

- https://orthanc.uclouvain.be/book/index.html

Useful sections from the official docs:

- Core server configuration and JSON keys
- DICOMweb plugin behavior
- OHIF plugin configuration
- Orthanc Web Viewer plugin configuration
- Orthanc Explorer 2 plugin configuration
- PostgreSQL backend configuration

When updating the local config, keep the Docker Compose service in
`../../docker-compose.yml` aligned with the same ports, volumes, and
runtime expectations.
