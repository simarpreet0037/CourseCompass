"""
Neo4j query helpers for bot operations.
"""
import logging
from typing import List, Dict, Optional
from CourseCompass.neo4j_driver import driver

logger = logging.getLogger(__name__)


def run_query(query: str, params: Optional[dict] = None) -> List[Dict]:
    """Execute a Cypher query and return results as list of dicts."""
    try:
        with driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]
    except Exception as e:
        logger.error(f"Neo4j query error: {e}")
        return [{"error": str(e)}]


def cypher_course_info(code: str) -> List[Dict]:
    """Get basic information about a course."""
    query = """
    MATCH (c:Course {code:$code})
    RETURN c.code AS code, c.title AS title, c.credits AS credits,
           c.level AS level, c.description AS description
    """
    return run_query(query, {"code": code})


def cypher_prereqs_full(code: str, depth: int = 3) -> Dict:
    """
    Retrieves a course and all of its prerequisite courses (direct and indirect),
    including each course's title and description, and the logical grouping type
    (AND / OR / CUSTOM) defined in the graph schema.

    Graph schema:
      (Course)-[:REQUIRES]->(PrerequisiteGroup)-[:HAS]->(Course)
    """
    query = f"""
    MATCH (target:Course {{code:$code}})-[:REQUIRES]->(g:PrerequisiteGroup)-[:HAS*1..{depth}]->(p:Course)
    WITH DISTINCT target, g, p
    RETURN DISTINCT
        target.code         AS target_code,
        target.title        AS target_title,
        target.description  AS target_desc,
        p.code              AS prereq_code,
        p.title             AS prereq_title,
        p.description       AS prereq_desc,
        g.type              AS group_type,
        g.recommended       AS recommended
    ORDER BY group_type, prereq_code
    """

    res = run_query(query, {"code": code})

    if not res or "error" in res[0]:
        return {"target": {}, "prereqs": []}

    target = {
        "code": res[0]["target_code"],
        "title": res[0]["target_title"],
        "description": res[0]["target_desc"],
    }

    prereqs = [
        {
            "code": r["prereq_code"],
            "title": r.get("prereq_title", ""),
            "description": r.get("prereq_desc", ""),
            "type": r.get("group_type") or "CUSTOM",
            "recommended": bool(r.get("recommended")),
        }
        for r in res if r.get("prereq_code")
    ]

    return {"target": target, "prereqs": prereqs}


def cypher_next_after(code: str) -> List[Dict]:
    """Get courses that have this course as a prerequisite."""
    query = """
    MATCH (next:Course)-[:REQUIRES]->(:PrerequisiteGroup)-[:HAS]->(c:Course {code:$code})
    RETURN DISTINCT next.code AS code, next.title AS title
    """
    return run_query(query, {"code": code})


def summarize_graph_context(limit: int = 50) -> str:
    """
    Collects a brief textual overview of available courses and their relationships.
    This helps the LLM reason about advising or general questions with real context.
    """
    try:
        with driver.session() as session:
            query = """
            MATCH (c:Course)
            OPTIONAL MATCH (c)-[:REQUIRES]->(g:PrerequisiteGroup)-[:HAS]->(p:Course)
            WITH c, collect(DISTINCT p.code) AS prereqs
            RETURN c.code AS code, c.title AS title, c.level AS level, c.credits AS credits, prereqs
            ORDER BY c.level, c.code
            LIMIT $limit
            """
            result = session.run(query, {"limit": limit})
            rows = [record.data() for record in result]
            if not rows:
                return "(no course data found in graph)"
            
            lines = []
            for r in rows:
                prereq_str = ", ".join(r["prereqs"]) if r["prereqs"] else "None"
                lines.append(
                    f"{r['code']} — {r['title']} | Level {r['level']} | {r['credits']} credits | Prereqs: {prereq_str}"
                )
            return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error summarizing graph context: {e}")
        return f"(graph context unavailable: {e})"
