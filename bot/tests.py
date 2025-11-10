from django.test import TestCase
from neo4j import GraphDatabase
from CourseCompass.CourseCompass.neo4j_driver import driver
from . import agent as advisor


class Neo4jIntegrationTests(TestCase):
    """
    Run with: python manage.py test bot
    These tests verify Neo4j connection, schema, and query integrity.
    """

    def test_neo4j_connection(self):
        """Check if Neo4j connection works."""
        print("\n🔍 Checking Neo4j connection...")
        try:
            with driver.session() as session:
                msg = session.run("RETURN 'Connected to Neo4j!' AS msg").single()["msg"]
            self.assertEqual(msg, "Connected to Neo4j!")
            print("✅ Connection successful")
        except Exception as e:
            self.fail(f"❌ Connection failed: {e}")

    def test_graph_schema(self):
        """Check graph schema — labels, relationship types, and node count."""
        print("\n🔍 Checking schema...")
        try:
            with driver.session() as session:
                labels = [r[0] for r in session.run("CALL db.labels()")]
                rels = [r[0] for r in session.run("CALL db.relationshipTypes()")]
                count = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]

            print(f"Node Labels: {labels}")
            print(f"Relationship Types: {rels}")
            print(f"Total Nodes: {count}")

            # Basic sanity checks
            self.assertIsInstance(labels, list)
            self.assertIsInstance(rels, list)
            self.assertGreaterEqual(count, 0)
        except Exception as e:
            self.fail(f"❌ Schema query failed: {e}")

    def test_query_functions(self):
        """Validate course query helpers in advisor.py."""
        print("\n🔍 Testing query functions...")
        sample_code = "CS110"  # replace with one that exists in your graph

        # 1️⃣ Test course info query
        res_info = advisor.cypher_course_info(sample_code)
        print("➡ cypher_course_info:", res_info)
        self.assertIsInstance(res_info, list)

        # 2️⃣ Test prerequisites query
        res_pre = advisor.cypher_prereqs_for(sample_code)
        print("➡ cypher_prereqs_for:", res_pre)
        self.assertIsInstance(res_pre, list)

        # 3️⃣ Test next-course query
        res_next = advisor.cypher_next_after(sample_code)
        print("➡ cypher_next_after:", res_next)
        self.assertIsInstance(res_next, list)
        
    def test_course_property_keys(self):
        print("\n🔍 Inspecting Course node properties...")
        with driver.session() as session:
            result = session.run("MATCH (c:Course) RETURN keys(c) AS props, c LIMIT 3")
            rows = [r["props"] for r in result]
            print(rows or "No Course nodes found!")
            self.assertTrue(rows, "No Course nodes found in Neo4j.")

