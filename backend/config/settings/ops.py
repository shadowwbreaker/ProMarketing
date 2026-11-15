"""Settings for one-off operations from CI (migrations) against the beta database (D-026).

Only what migrate needs: the database. Never used to serve requests.
"""
from .base import *  # noqa: F403

DEBUG = False
