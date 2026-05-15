"""
Neo4j query helpers for bot operations.
"""
import logging
from typing import List, Dict, Optional
from CourseCompass.neo4j_driver import get_driver

logger = logging.getLogger(__name__)


def run_query(query: str, params: Optional[dict] = None) -> List[Dict]:
    """Execute a Cypher query and return results as list of dicts."""
    try:
        driver = get_driver()
        if driver is None:
            return [{"error": "Neo4j is not configured"}]
        with driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]
    except Exception as e:
        logger.error(f"Neo4j query error: {e}")
        return [{"error": str(e)}]


def cypher_course_info(code: str) -> List[Dict]:
    """Get basic information about a course."""
    # Normalize course code by removing spaces (e.g., 'CS 115' -> 'CS115')
    code = code.replace(' ', '').strip().upper()
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
    # Normalize course code by removing spaces (e.g., 'CS 115' -> 'CS115')
    code = code.replace(' ', '').strip().upper()
    # Keep depth in a safe and practical range to avoid expensive traversals.
    depth = max(1, min(int(depth), 8))
    max_rel_len = depth * 2

    # Neo4j does not allow parameters in variable-length relationship bounds.
    query = f"""
    MATCH (target:Course {{code:$code}})
    MATCH p=(target)-[:REQUIRES|HAS*2..{max_rel_len}]->(pr:Course)
    WITH DISTINCT target, p, pr
    UNWIND range(0, size(nodes(p)) - 3, 2) AS idx
    WITH DISTINCT
        target,
        pr,
        nodes(p)[idx]     AS dependent,
        nodes(p)[idx + 1] AS grp,
        nodes(p)[idx + 2] AS prereq
    RETURN DISTINCT
        target.code            AS target_code,
        target.title           AS target_title,
        target.description     AS target_desc,
        pr.code                AS path_prereq_code,
        pr.title               AS path_prereq_title,
        pr.description         AS path_prereq_desc,
        prereq.code            AS edge_prereq_code,
        prereq.title           AS edge_prereq_title,
        prereq.description     AS edge_prereq_desc,
        dependent.code         AS edge_dependent_code,
        dependent.title        AS edge_dependent_title,
        grp.type               AS group_type,
        grp.recommended        AS recommended
    ORDER BY edge_prereq_code, edge_dependent_code
    """

    res = run_query(query, {"code": code, "max_rel_len": max_rel_len})

    if not res or "error" in res[0]:
        return {"target": {}, "prereqs": []}

    target = {
        "code": res[0]["target_code"],
        "title": res[0]["target_title"],
        "description": res[0]["target_desc"],
    }

    prereq_map = {}
    edge_map = {}

    for r in res:
        path_prereq_code = r.get("path_prereq_code")
        if path_prereq_code and path_prereq_code not in prereq_map:
            prereq_map[path_prereq_code] = {
                "code": path_prereq_code,
                "title": r.get("path_prereq_title", ""),
                "description": r.get("path_prereq_desc", ""),
                "type": r.get("group_type") or "CUSTOM",
                "recommended": bool(r.get("recommended")),
            }

        edge_prereq_code = r.get("edge_prereq_code")
        edge_dependent_code = r.get("edge_dependent_code")
        if edge_prereq_code and edge_dependent_code:
            edge_key = (edge_prereq_code, edge_dependent_code)
            if edge_key not in edge_map:
                edge_map[edge_key] = {
                    "source": edge_prereq_code,
                    "target": edge_dependent_code,
                    "type": r.get("group_type") or "CUSTOM",
                    "recommended": bool(r.get("recommended")),
                }

    prereqs = sorted(prereq_map.values(), key=lambda item: item["code"])
    graph_edges = sorted(
        edge_map.values(),
        key=lambda item: (item["target"], item["source"]),
    )

    return {"target": target, "prereqs": prereqs, "graph_edges": graph_edges}


def cypher_next_after(code: str) -> List[Dict]:
    """Get courses that have this course as a prerequisite."""
    # Normalize course code by removing spaces (e.g., 'CS 115' -> 'CS115')
    code = code.replace(' ', '').strip().upper()
    query = """
    MATCH (next:Course)-[:REQUIRES]->(:PrerequisiteGroup)-[:HAS]->(c:Course {code:$code})
    RETURN DISTINCT next.code AS code, next.title AS title
    """
    return run_query(query, {"code": code})


def cypher_neighborhood(code: str) -> Dict:
    """
    Get a course's direct prerequisites and direct next courses in one call.
    Used to render the neighbourhood graph for course_info queries.
    """
    code = code.replace(' ', '').strip().upper()
    try:
        driver = get_driver()
        if driver is None:
            return {"focus": {}, "prereqs": [], "next_courses": []}
        with driver.session() as session:
            result = session.run("""
                MATCH (c:Course {code: $code})
                OPTIONAL MATCH (c)-[:REQUIRES]->(:PrerequisiteGroup)-[:HAS]->(prereq:Course)
                OPTIONAL MATCH (next:Course)-[:REQUIRES]->(:PrerequisiteGroup)-[:HAS]->(c)
                RETURN
                    c.code        AS focus_code,
                    c.title       AS focus_title,
                    c.description AS focus_desc,
                    c.credits     AS focus_credits,
                    c.level       AS focus_level,
                    collect(DISTINCT prereq.code) AS prereq_codes,
                    collect(DISTINCT next.code)   AS next_codes
            """, code=code).single()

            if not result:
                return {"focus": {}, "prereqs": [], "next_courses": []}

            return {
                "focus": {
                    "code": result["focus_code"],
                    "title": result["focus_title"],
                    "description": result["focus_desc"],
                    "credits": result["focus_credits"],
                    "level": result["focus_level"],
                },
                "prereqs": [c for c in result["prereq_codes"] if c],
                "next_courses": [c for c in result["next_codes"] if c],
            }
    except Exception as e:
        logger.error(f"Neighbourhood query error: {e}")
        return {"focus": {}, "prereqs": [], "next_courses": []}


def cypher_courses_by_level(limit: int = 60) -> List[Dict]:
    """
    Return all courses ordered by academic level, plus direct prerequisite edges
    between them.  Used to render the degree-roadmap graph for advising queries.
    """
    query = """
    MATCH (c:Course)
    OPTIONAL MATCH (c)-[:REQUIRES]->(:PrerequisiteGroup)-[:HAS]->(prereq:Course)
    WITH c, collect(DISTINCT prereq.code) AS prereq_codes
    RETURN c.code AS code, c.title AS title, c.level AS level, prereq_codes
    ORDER BY c.level, c.code
    LIMIT $limit
    """
    return run_query(query, {"limit": limit})


def summarize_graph_context(limit: int = 50) -> str:
    """
    Collects a brief textual overview of available courses and their relationships.
    This helps the LLM reason about advising or general questions with real context.
    """
    try:
        driver = get_driver()
        if driver is None:
            return "(graph context unavailable: Neo4j is not configured)"
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
