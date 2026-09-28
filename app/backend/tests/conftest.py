"""Shared test configuration.

Tests must never inherit a developer or deployment DATABASE_URL from .env.
The application-level persistence tests are intentionally local/SQLite unless a
test constructs a PostgreSQL-backed PersistenceDatabase explicitly.
"""

import os

# conftest is imported before test modules, so this overrides .env before
# app.core.config creates its module-level Settings instance.
os.environ["DATABASE_URL"] = ""
