from django.shortcuts import render, redirect
from .forms import CourseForm   # Import the Course Form
from .neo4j_driver import driver # Import the Neo4j driver

from django.contrib import messages

def add_course(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            code = data['code'].strip().upper()
            title = data['title'].strip()
            credits = data['credits']
            level = int(data['level'])
            prereqs = [p.strip().upper() for p in data['prerequisites'].split(',') if p.strip()]

            with driver.session() as session:
                # 1. Check if any prereqs don't exist
                missing_prereqs = []
                for prereq in prereqs:
                    exists = session.run("MATCH (c:Course {code: $code}) RETURN c", code=prereq).single()
                    if not exists:
                        missing_prereqs.append(prereq)

                if missing_prereqs:
                    messages.error(request, f"The following prerequisites do not exist: {', '.join(missing_prereqs)}")
                    return render(request, 'courses/add_course.html', {'form': form})

                # 2. Check for cycles (course already reachable from prereq)
                for prereq in prereqs:
                    path = session.run(
                        """
                        MATCH (start:Course {code: $code}), (end:Course {code: $prereq})
                        RETURN EXISTS((start)-[:PREREQUISITE_OF*]->(end)) AS createsCycle
                        """,
                        code=code,
                        prereq=prereq
                    ).single()
                    if path and path['createsCycle']:
                        messages.error(request, f"Adding '{prereq}' as a prerequisite creates a cycle.")
                        return render(request, 'courses/add_course.html', {'form': form})

                # 3. Add course and relationships safely
                def add_course_to_graph(tx):
                    tx.run(
                        "MERGE (c:Course {code: $code}) "
                        "SET c.title = $title, c.credits = $credits, c.level = $level",
                        code=code, title=title, credits=credits, level=level
                    )
                    for prereq in prereqs:
                        tx.run(
                            "MATCH (p:Course {code: $prereq}), (c:Course {code: $code}) "
                            "MERGE (p)-[:PREREQUISITE_OF]->(c)",
                            prereq=prereq, code=code
                        )
                session.write_transaction(add_course_to_graph)

            messages.success(request, f"Course '{code}' added successfully.")
            return redirect('view_courses')
    else:
        form = CourseForm()

    return render(request, 'courses/add_course.html', {'form': form})




def view_courses(request):
    with driver.session() as session:
        result = session.run(
            """
            MATCH (a:Course)
            OPTIONAL MATCH (a)<-[:PREREQUISITE_OF]-(p:Course)
            RETURN a.code AS course_code, a.title AS title, COLLECT(p.code) AS prerequisites
            ORDER BY a.code
            """
        )
        courses = result.data()

    nodes = []
    edges = []
    node_set = set()

    for course in courses:
        code = course['course_code']
        title = course['title']
        prerequisites = course['prerequisites']

        if code not in node_set:
            nodes.append({'id': code, 'label': f"{code}\n{title}"})
            node_set.add(code)

        for prereq in prerequisites:
            if prereq not in node_set:
                nodes.append({'id': prereq, 'label': prereq})
                node_set.add(prereq)
            edges.append({'from': prereq, 'to': code})  # Edge from prereq to course

    return render(request, 'courses/view_graph.html', {
        'nodes': nodes,
        'edges': edges,
        'courses': courses  # Optional: for table rendering
    })

