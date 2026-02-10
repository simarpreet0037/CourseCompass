"""
Neo4j Database Connection Module
--------------------------------
Manages Neo4j database connection with proper SSL handling and connection pooling.
"""

from neo4j import GraphDatabase
import ssl
import os
import logging

logger = logging.getLogger(__name__)

# Neo4j credentials (loaded from environment)
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

# SSL Configuration
# In production, set NEO4J_SKIP_SSL_VERIFY=false (default)
# Only set to 'true' for local development with self-signed certs
SKIP_SSL_VERIFY = os.getenv("NEO4J_SKIP_SSL_VERIFY", "false").lower() == "true"


def create_driver():
    """Create and configure Neo4j driver with appropriate SSL settings."""
    if not NEO4J_URI:
        logger.warning("NEO4J_URI not set. Database features will be unavailable.")
        return None
    
    driver_kwargs = {
        "auth": (NEO4J_USER, NEO4J_PASS),
        "max_connection_lifetime": 3600,  # 1 hour
        "max_connection_pool_size": 50,
        "connection_acquisition_timeout": 60,
    }
    
    if SKIP_SSL_VERIFY:
        # WARNING: Only for development with self-signed certificates
        logger.warning("SSL verification disabled - NOT SAFE FOR PRODUCTION")
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        driver_kwargs["ssl_context"] = ssl_context
    
    try:
        drv = GraphDatabase.driver(NEO4J_URI, **driver_kwargs)
        logger.info("Neo4j connection established successfully")
        return drv
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        raise


# Initialize driver (lazy loading pattern)
_driver = None


def get_driver():
    """Get or create the Neo4j driver instance."""
    global _driver
    if _driver is None:
        _driver = create_driver()
    return _driver


# For backward compatibility
driver = create_driver()


def close_driver():
    """Close the Neo4j driver connection."""
    global _driver, driver
    if _driver:
        _driver.close()
        _driver = None
    if driver:
        driver.close()
        driver = None
    logger.info("Neo4j connection closed")
