---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/test/gold_set/auth_service.md"
last_updated: "2026-06-11T06:36:30.648646+00:00"
entities:
  - "user-database"
---
# User Database

## Description
The User Database is a PostgreSQL instance dedicated to storing user profiles and related authentication data.

## Type
PostgreSQL

## Consumers
*   [[wiki/services/auth-service]] - Relies on this database to retrieve user profiles.