from neo4j import GraphDatabase

import ssl

# Database Aura credentials
NEO4J_URI = "neo4j://c76e87f4.databases.neo4j.io"
NEO4J_USER = "neo4j"
NEO4J_PASS = "wBzMWTktgsRPzcjtjta9KXQ3xEmU-QbKiN-kvUv71IE"

# Create an SSL context that skips certificate verification
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS), ssl_context=ssl_context)

# Test connection
driver.verify_connectivity()
with driver.session(database="neo4j") as session:
    result = session.run("RETURN 1 AS test")
    print("Connection successful, test result:", result.single()["test"])