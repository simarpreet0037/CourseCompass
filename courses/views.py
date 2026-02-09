"""
Course management views.
"""
import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import CourseForm
from .services import (
    parse_prereq_groups_from_post,
    validate_prereq_courses,
    create_prereq_groups,
    delete_course_prereq_groups,
    get_all_prereq_codes,
    create_or_update_course,
    get_course_prereq_groups,
)
from CourseCompass.neo4j_driver import driver

logger = logging.getLogger(__name__)


def add_course(request):
    """Add a new course to the database."""
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            code = data['code'].strip().upper()
            title = data['title'].strip()
            credits = data['credits']
            level = int(data['level'])
            description = data['description'].strip()

            # Parse prerequisite groups from POST data
            required_groups, recommended_groups, custom_groups = parse_prereq_groups_from_post(request.POST)
            all_prereq_codes = get_all_prereq_codes(required_groups, recommended_groups, custom_groups)

            with driver.session() as session:
                # Validate prerequisite courses exist
                missing = validate_prereq_courses(session, all_prereq_codes)

                if missing:
                    messages.error(request, f"Missing prerequisite courses: {', '.join(missing)}")
                    return render(request, 'courses/course_form.html', {
                        'form': form,
                        'edit_mode': False,
                        'required_groups': required_groups,
                        'recommended_groups': recommended_groups,
                        'custom_groups': custom_groups
                    })

                # Create or update course
                create_or_update_course(session, code, title, credits, level, description)
                
                # Create prerequisite groups
                create_prereq_groups(session, code, required_groups, recommended_groups, custom_groups)

            logger.info(f"Course '{code}' added successfully")
            messages.success(request, f"Course '{code}' added successfully.")
            return redirect('view_courses')
    else:
        form = CourseForm()

    return render(request, 'courses/course_form.html', {
        'form': form,
        'edit_mode': False,
        'required_groups': [],
        'recommended_groups': [],
        'custom_groups': []
    })


def view_courses(request):
    """View all courses and their prerequisites graph."""
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Course)
            OPTIONAL MATCH (c)-[:REQUIRES]->(g:PrerequisiteGroup)-[:HAS]->(p:Course)
            RETURN c.code AS course_code, 
                   c.title AS title, 
                   c.description AS description,
                   COLLECT(DISTINCT p.code) AS prerequisites
            ORDER BY c.code
        """)

        courses = result.data()

    nodes = []
    edges = []
    node_set = set()

    for course in courses:
        code = course['course_code']
        title = course['title']
        description = course.get('description', '') or ''
        prerequisites = course['prerequisites']

        if code not in node_set:
            nodes.append({
                'id': code,
                'label': f"{code}\n{title}",
                'description': description
            })
            node_set.add(code)

        for prereq in prerequisites:
            if prereq and prereq not in node_set:
                nodes.append({'id': prereq, 'label': prereq, 'description': ''})
                node_set.add(prereq)
            if prereq:
                edges.append({'from': prereq, 'to': code})

    return render(request, 'courses/view_graph.html', {
        'nodes': nodes,
        'edges': edges,
        'courses': courses
    })


def edit_course(request, code):
    """Edit an existing course."""
    with driver.session() as session:
        course_data = session.run("""
            MATCH (c:Course {code: $code})
            RETURN c.title AS title, 
                   c.credits AS credits, 
                   c.level AS level,
                   c.description AS description
        """, code=code).single()

        if not course_data:
            messages.error(request, "Course not found.")
            return redirect('view_courses')

        if request.method == 'POST':
            form = CourseForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                title = data['title']
                credits = data['credits']
                level = int(data['level'])
                description = data['description'].strip()

                # Parse prerequisite groups from POST data
                required_groups, recommended_groups, custom_groups = parse_prereq_groups_from_post(request.POST)
                all_prereq_codes = get_all_prereq_codes(required_groups, recommended_groups, custom_groups)

                # Validate prerequisite courses exist
                missing = validate_prereq_courses(session, all_prereq_codes)

                if missing:
                    messages.error(request, f"Missing prerequisite courses: {', '.join(missing)}")
                    return render(request, 'courses/course_form.html', {
                        'form': form,
                        'edit_mode': True,
                        'required_groups': required_groups,
                        'recommended_groups': recommended_groups,
                        'custom_groups': custom_groups,
                        'code': code
                    })

                # Update course
                create_or_update_course(session, code, title, credits, level, description)

                # Delete old prerequisite groups and create new ones
                delete_course_prereq_groups(session, code)
                create_prereq_groups(session, code, required_groups, recommended_groups, custom_groups)

                logger.info(f"Course '{code}' updated successfully")
                messages.success(request, f"Course '{code}' updated successfully.")
                return redirect('view_courses')
        else:
            form = CourseForm(initial={
                'code': code,
                'title': course_data['title'],
                'credits': course_data['credits'],
                'level': course_data['level'],
                'description': course_data.get('description', '')
            })
            form.fields['code'].widget.attrs['readonly'] = True

            # Get existing prerequisite groups
            required_groups, recommended_groups, custom_groups = get_course_prereq_groups(session, code)

            return render(request, 'courses/course_form.html', {
                'form': form,
                'edit_mode': True,
                'required_groups': required_groups,
                'recommended_groups': recommended_groups,
                'custom_groups': custom_groups,
                'code': code
            })


def delete_course(request, code):
    """Delete a course and its prerequisite groups."""
    with driver.session() as session:
        course_exists = session.run("MATCH (c:Course {code: $code}) RETURN c", code=code).single()
        if not course_exists:
            messages.error(request, f"Course '{code}' not found.")
            return redirect('view_courses')

        session.run("""
            MATCH (c:Course {code: $code})
            OPTIONAL MATCH (c)-[:REQUIRES]->(g:PrerequisiteGroup)
            DETACH DELETE c, g
        """, code=code)

    logger.info(f"Course '{code}' deleted successfully")
    messages.success(request, f"Course '{code}' deleted successfully.")
    return redirect('view_courses')
