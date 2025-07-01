from neo4j import GraphDatabase
import ssl

uri = "neo4j://c76e87f4.databases.neo4j.io"
username = "neo4j"
password = "wBzMWTktgsRPzcjtjta9KXQ3xEmU-QbKiN-kvUv71IE"

# Create an SSL context that skips certificate verification
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

driver = GraphDatabase.driver(uri, auth=(username, password), ssl_context=ssl_context)

# Test connection
driver.verify_connectivity()

with driver.session(database="neo4j") as session:
    result = session.run("RETURN 1 AS test")
    print("Connection successful, test result:", result.single()["test"])
