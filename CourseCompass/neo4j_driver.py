"""
Neo4j Database Connection Script
--------------------------------
This script connects to the Neo4j Aura database using the official Neo4j Python driver.
This contanins the graph of the various courses and their prerequisites.
It bypasses SSL certificate verification (use with caution in production) to handle 
self-signed certificates or local development environments.

Functionality:
1. Defines database connection credentials.
2. Configures an SSL context to skip certificate validation.
3. Establishes a connection to the Neo4j instance.
4. Verifies the connection.
5. Runs a simple test query to confirm connectivity.
"""

from neo4j import GraphDatabase
import ssl
import os

# Neo4j Aura credentials (loaded from environment)
NEO4J_URI = os.getenv("NEO4J_URI", "database_uri")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "database_usr")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "database_pass")



# Create an SSL context that disables certificate verification
# WARNING: This is insecure for production. 
# Only use when testing or connecting to a trusted source with self-signed certs.
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Initialize the Neo4j driver with the provided credentials and SSL settings
driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASS),
    ssl_context=ssl_context
)

# Verify connectivity to the database
driver.verify_connectivity()

# Open a session and run a simple query to confirm the connection
with driver.session(database="neo4j") as session:
    result = session.run("RETURN 1 AS test")
    print("Connection successful, test result:", result.single()["test"])
