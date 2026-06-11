# Auth Service

The Auth Service handles user authentication and session management. It is owned by the Platform Team.
It relies on the User Database (PostgreSQL) to retrieve user profiles.
The Auth Service exposes REST APIs for login and token verification.
It depends on Redis for token caching.
