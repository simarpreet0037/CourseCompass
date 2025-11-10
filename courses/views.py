import re
import uuid
import re
import uuid
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import CourseForm
from CourseCompass.neo4j_driver import driver


def add_course(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            code = data['code'].strip().upper()
            title = data['title'].strip()
            credits = data['credits']
            level = int(data['level'])
            description = data['description'].strip()

            required_groups = []
            recommended_groups = []
            custom_groups = []

            for key, value in request.POST.items():
                match_req = re.match(r'required_courses_(\d+)', key)
                match_rec = re.match(r'recommended_courses_(\d+)', key)
                match_cust = re.match(r'custom_courses_(\d+)', key)

                if match_req:
                    index = match_req.group(1)
                    courses = [c.strip().upper() for c in value.split(',') if c.strip()]
                    group_type = request.POST.get(f'required_group_type_{index}', 'AND')
                    if courses:
                        required_groups.append({'type': group_type, 'courses': courses})

                if match_rec:
                    index = match_rec.group(1)
                    courses = [c.strip().upper() for c in value.split(',') if c.strip()]
                    group_type = request.POST.get(f'recommended_group_type_{index}', 'OR')
                    if courses:
                        recommended_groups.append({'type': group_type, 'courses': courses})

                if match_cust:
                    index = match_cust.group(1)
                    courses = [c.strip().upper() for c in value.split(',') if c.strip()]
                    group_type = request.POST.get(f'custom_group_type_{index}', '').strip()
                    if courses and group_type:
                        custom_groups.append({'type': group_type, 'courses': courses})

            all_prereq_codes = {c for group in (required_groups + recommended_groups + custom_groups) for c in group['courses']}

            with driver.session() as session:
                missing = []
                for code_check in all_prereq_codes:
                    exists = session.run("MATCH (c:Course {code: $code}) RETURN c", code=code_check).single()
                missing = []
                for code_check in all_prereq_codes:
                    exists = session.run("MATCH (c:Course {code: $code}) RETURN c", code=code_check).single()
                    if not exists:
                        missing.append(code_check)
                        missing.append(code_check)

                if missing:
                    messages.error(request, f"Missing prerequisite courses: {', '.join(missing)}")
                    return render(request, 'courses/course_form.html', {
                        'form': form,
                        'edit_mode': False,
                        'required_groups': required_groups,
                        'recommended_groups': recommended_groups,
                        'custom_groups': custom_groups
                    })

                session.run("""
                    MERGE (c:Course {code: $code})
                    SET c.title = $title, 
                        c.credits = $credits, 
                        c.level = $level,
                        c.description = $description
                """, code=code, title=title, credits=credits, level=level, description=description)

                def add_prereq_group(tx, groups, is_recommended):
                    for group in groups:
                        group_type = group['type']
                        group_id = str(uuid.uuid4())

                        tx.run("""
                            MATCH (c:Course {code: $course_code})
                            CREATE (g:PrerequisiteGroup {id: $group_id, type: $group_type, recommended: $is_rec})
                            MERGE (c)-[:REQUIRES]->(g)
                        """, course_code=code, group_id=group_id, group_type=group_type, is_rec=is_recommended)

                        for course in group['courses']:
                            tx.run("""
                                MATCH (p:Course {code: $prereq})
                                MATCH (g:PrerequisiteGroup {id: $group_id})
                                MERGE (g)-[:HAS]->(p)
                            """, group_id=group_id, prereq=course)

                session.write_transaction(add_prereq_group, required_groups, False)
                session.write_transaction(add_prereq_group, recommended_groups, True)
                session.write_transaction(add_prereq_group, custom_groups, None)

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
                edges.append({'from': prereq, 'to': code})  # Prereq → Course

    return render(request, 'courses/view_graph.html', {
        'nodes': nodes,
        'edges': edges,
        'courses': courses
    })


def edit_course(request, code):
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

                required_groups = []
                recommended_groups = []
                custom_groups = []

                for key, value in request.POST.items():
                    match_req = re.match(r'required_courses_(\d+)', key)
                    match_rec = re.match(r'recommended_courses_(\d+)', key)
                    match_cust = re.match(r'custom_courses_(\d+)', key)

                    if match_req:
                        index = match_req.group(1)
                        courses = [c.strip().upper() for c in value.split(',') if c.strip()]
                        group_type = request.POST.get(f'required_group_type_{index}', 'AND')
                        if courses:
                            required_groups.append({'type': group_type, 'courses': courses})

                    if match_rec:
                        index = match_rec.group(1)
                        courses = [c.strip().upper() for c in value.split(',') if c.strip()]
                        group_type = request.POST.get(f'recommended_group_type_{index}', 'OR')
                        if courses:
                            recommended_groups.append({'type': group_type, 'courses': courses})

                    if match_cust:
                        index = match_cust.group(1)
                        courses = [c.strip().upper() for c in value.split(',') if c.strip()]
                        group_type = request.POST.get(f'custom_group_type_{index}', '').strip()
                        if courses and group_type:
                            custom_groups.append({'type': group_type, 'courses': courses})

                all_prereq_codes = {c for group in (required_groups + recommended_groups + custom_groups) for c in group['courses']}

                missing = []
                for code_check in all_prereq_codes:
                    exists = session.run("MATCH (c:Course {code: $code}) RETURN c", code=code_check).single()
                    if not exists:
                        missing.append(code_check)

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

                session.run("""
                    MATCH (c:Course {code: $code})
                    SET c.title = $title, 
                        c.credits = $credits, 
                        c.level = $level,
                        c.description = $description
                """, code=code, title=title, credits=credits, level=level, description=description)

                session.run("""
                    MATCH (c:Course {code: $code})-[:REQUIRES]->(g:PrerequisiteGroup)
                    DETACH DELETE g
                """, code=code)

                def add_prereq_group(tx, groups, is_recommended):
                    for group in groups:
                        group_type = group['type']
                        group_id = str(uuid.uuid4())

                        tx.run("""
                            MATCH (c:Course {code: $course_code})
                            CREATE (g:PrerequisiteGroup {id: $group_id, type: $group_type, recommended: $is_rec})
                            MERGE (c)-[:REQUIRES]->(g)
                        """, course_code=code, group_id=group_id, group_type=group_type, is_rec=is_recommended)

                        for course in group['courses']:
                            tx.run("""
                                MATCH (p:Course {code: $prereq})
                                MATCH (g:PrerequisiteGroup {id: $group_id})
                                MERGE (g)-[:HAS]->(p)
                            """, group_id=group_id, prereq=course)

                session.write_transaction(add_prereq_group, required_groups, False)
                session.write_transaction(add_prereq_group, recommended_groups, True)
                session.write_transaction(add_prereq_group, custom_groups, None)

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

            return render(request, 'courses/course_form.html', {
                'form': form,
                'edit_mode': True,
                'required_groups': required_groups,
                'recommended_groups': recommended_groups,
                'custom_groups': custom_groups,
                'code': code
            })


def delete_course(request, code):
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

    messages.success(request, f"Course '{code}' deleted successfully.")
    return redirect('view_courses')
