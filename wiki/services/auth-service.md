---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/test/gold_set/payment_pipeline.md"
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/test/gold_set/auth_service.md"
last_updated: "2026-06-11T06:36:18.660657+00:00"
entities:
  - "auth-service"
---
# Auth Service

## Purpose
The Auth Service handles user authentication and session management.

## Owners
The Platform Team. [[wiki/person/platform-team]]

## APIs
The Auth Service exposes REST APIs for login and token verification.

## Dependencies
*   User Database (PostgreSQL) [[wiki/services/user-database]]
*   Redis (for token caching) [[wiki/services/redis]]

## Consumers
*   [[wiki/pipelines/payment-processing-pipeline]] (Authenticates payment requests for the pipeline)