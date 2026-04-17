"""
Course management services - shared business logic for course operations.
"""
import re
import uuid
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


def parse_prereq_groups_from_post(request_post: Dict) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Parse prerequisite groups from POST data.
    
    Returns:
        Tuple of (required_groups, recommended_groups, custom_groups)
    """
    required_groups = []
    recommended_groups = []
    custom_groups = []

    for key, value in request_post.items():
        match_req = re.match(r'required_courses_(\d+)', key)
        match_rec = re.match(r'recommended_courses_(\d+)', key)
        match_cust = re.match(r'custom_courses_(\d+)', key)

        if match_req:
            index = match_req.group(1)
            courses = [c.strip().upper() for c in value.split(',') if c.strip()]
            group_type = request_post.get(f'required_group_type_{index}', 'AND')
            if courses:
                required_groups.append({'type': group_type, 'courses': courses})

        if match_rec:
            index = match_rec.group(1)
            courses = [c.strip().upper() for c in value.split(',') if c.strip()]
            group_type = request_post.get(f'recommended_group_type_{index}', 'OR')
            if courses:
                recommended_groups.append({'type': group_type, 'courses': courses})

        if match_cust:
            index = match_cust.group(1)
            courses = [c.strip().upper() for c in value.split(',') if c.strip()]
            group_type = request_post.get(f'custom_group_type_{index}', '').strip()
            if courses and group_type:
                custom_groups.append({'type': group_type, 'courses': courses})

    return required_groups, recommended_groups, custom_groups


def validate_prereq_courses(session, codes: set) -> List[str]:
    """
    Validate that all prerequisite course codes exist in the database.
    
    Args:
        session: Neo4j session
        codes: Set of course codes to validate
        
    Returns:
        List of missing course codes
    """
    missing = []
    for code_check in codes:
        exists = session.run("MATCH (c:Course {code: $code}) RETURN c", code=code_check).single()
        if not exists:
            missing.append(code_check)
    return missing


def create_prereq_groups(session, course_code: str, 
                         required_groups: List[Dict], 
                         recommended_groups: List[Dict], 
                         custom_groups: List[Dict]) -> None:
    """
    Create prerequisite groups in the database for a course.
    
    Args:
        session: Neo4j session
        course_code: The course code to add prerequisites for
        required_groups: List of required prerequisite groups
        recommended_groups: List of recommended prerequisite groups
        custom_groups: List of custom prerequisite groups
    """
    def add_prereq_group(tx, groups: List[Dict], is_recommended: Optional[bool]):
        for group in groups:
            group_type = group['type']
            group_id = str(uuid.uuid4())

            tx.run("""
                MATCH (c:Course {code: $course_code})
                CREATE (g:PrerequisiteGroup {id: $group_id, type: $group_type, recommended: $is_rec})
                MERGE (c)-[:REQUIRES]->(g)
            """, course_code=course_code, group_id=group_id, group_type=group_type, is_rec=is_recommended)

            for course in group['courses']:
                tx.run("""
                    MATCH (p:Course {code: $prereq})
                    MATCH (g:PrerequisiteGroup {id: $group_id})
                    MERGE (g)-[:HAS]->(p)
                """, group_id=group_id, prereq=course)

    # Run all group writes in one managed transaction per request.
    session.execute_write(add_prereq_group, required_groups, False)
    session.execute_write(add_prereq_group, recommended_groups, True)
    session.execute_write(add_prereq_group, custom_groups, None)


def delete_course_prereq_groups(session, course_code: str) -> None:
    """Delete all prerequisite groups for a course."""
    session.run("""
        MATCH (c:Course {code: $code})-[:REQUIRES]->(g:PrerequisiteGroup)
        DETACH DELETE g
    """, code=course_code)


def get_all_prereq_codes(required_groups: List[Dict], 
                         recommended_groups: List[Dict], 
                         custom_groups: List[Dict]) -> set:
    """Get all unique prerequisite course codes from all groups."""
    return {c for group in (required_groups + recommended_groups + custom_groups) 
            for c in group['courses']}


def create_or_update_course(session, code: str, title: str, credits: int, 
                            level: int, description: str) -> None:
    """Create or update a course in the database."""
    session.run("""
        MERGE (c:Course {code: $code})
        SET c.title = $title, 
            c.credits = $credits, 
            c.level = $level,
            c.description = $description
    """, code=code, title=title, credits=credits, level=level, description=description)


def get_course_prereq_groups(session, code: str) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Get existing prerequisite groups for a course.
    
    Returns:
        Tuple of (required_groups, recommended_groups, custom_groups)
    """
    required_groups = []
    recommended_groups = []
    custom_groups = []

    results = session.run("""
        MATCH (c:Course {code: $code})-[:REQUIRES]->(g:PrerequisiteGroup)
        OPTIONAL MATCH (g)-[:HAS]->(p:Course)
        RETURN g.type AS type, g.recommended AS recommended, COLLECT(p.code) AS courses
    """, code=code)

    for record in results:
        group = {'type': record['type'], 'courses': record['courses']}
        if record['recommended'] is True:
            recommended_groups.append(group)
        elif record['recommended'] is False:
            required_groups.append(group)
        else:
            custom_groups.append(group)

    return required_groups, recommended_groups, custom_groups
