"""MySQL connection helper: one place that knows how to connect."""
import mysql.connector

import config


def get_db():
    """Open a new connection using the settings from the environment."""
    return mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
    )
