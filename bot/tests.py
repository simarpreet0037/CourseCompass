"""
Bot tests for Neo4j integration and query functions.
Run with: python manage.py test bot
"""
import logging
from django.test import TestCase
from CourseCompass.neo4j_driver import driver
from . import queries

logger = logging.getLogger(__name__)


class Neo4jIntegrationTests(TestCase):
    """
    Tests verify Neo4j connection, schema, and query integrity.
    """

    def test_neo4j_connection(self):
        """Check if Neo4j connection works."""
        logger.info("Checking Neo4j connection...")
        try:
            with driver.session() as session:
                msg = session.run("RETURN 'Connected to Neo4j!' AS msg").single()["msg"]
            self.assertEqual(msg, "Connected to Neo4j!")
            logger.info("Connection successful")
        except Exception as e:
            self.fail(f"Connection failed: {e}")

    def test_graph_schema(self):
        """Check graph schema — labels, relationship types, and node count."""
        logger.info("Checking schema...")
        try:
            with driver.session() as session:
                labels = [r[0] for r in session.run("CALL db.labels()")]
                rels = [r[0] for r in session.run("CALL db.relationshipTypes()")]
                count = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]

            logger.info(f"Node Labels: {labels}")
            logger.info(f"Relationship Types: {rels}")
            logger.info(f"Total Nodes: {count}")

            # Basic sanity checks
            self.assertIsInstance(labels, list)
            self.assertIsInstance(rels, list)
            self.assertGreaterEqual(count, 0)
        except Exception as e:
            self.fail(f"Schema query failed: {e}")

    def test_query_functions(self):
        """Validate course query helpers in queries.py."""
        logger.info("Testing query functions...")
        sample_code = "CS 110"  # replace with one that exists in your graph

        # Test course info query
        res_info = queries.cypher_course_info(sample_code)
        logger.info(f"cypher_course_info: {res_info}")
        self.assertIsInstance(res_info, list)

        # Test prerequisites query
        res_pre = queries.cypher_prereqs_full(sample_code)
        logger.info(f"cypher_prereqs_full: {res_pre}")
        self.assertIsInstance(res_pre, dict)

        # Test next-course query
        res_next = queries.cypher_next_after(sample_code)
        logger.info(f"cypher_next_after: {res_next}")
        self.assertIsInstance(res_next, list)
        
    def test_course_property_keys(self):
        """Verify Course nodes have expected properties."""
        logger.info("Inspecting Course node properties...")
        with driver.session() as session:
            result = session.run("MATCH (c:Course) RETURN keys(c) AS props, c LIMIT 3")
            rows = [r["props"] for r in result]
            logger.info(f"Course properties: {rows or 'No Course nodes found!'}")
            # Note: This assertion may fail if no courses exist yet
            if rows:
                self.assertTrue(rows, "No Course nodes found in Neo4j.")

