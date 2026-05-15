"""
Next course query intent handler.
"""
import logging
import json
from typing import Optional

from ..queries import cypher_next_after
from ..prompts import NEXT_COURSE_PROMPT
from ..groqllm import GroqLLM
from ..config import API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

# Initialize LLM
llm = GroqLLM(api_key=API_KEY, model=MODEL_NAME)


def render_next_course_graph(course_code: str, next_courses: list) -> str:
    """
    Render a forward-dependency graph: queried course at the top,
    courses you can take next fanning out below it.
    graph-type='next' tells the JS renderer to pin the source node to the top.
    """
    nodes = [{"data": {"id": course_code, "label": course_code, "kind": "source"}}]
    edges = []

    for n in next_courses:
        code = n.get("code")
        if not code:
            continue
        nodes.append({"data": {"id": code, "label": code, "kind": "next"}})
        edges.append({"data": {"id": f"{course_code}->{code}", "source": course_code, "target": code}})

    graph_data = json.dumps({"elements": {"nodes": nodes, "edges": edges}})
    height = max(220, 80 + len(next_courses) * 60)

    return f"""
    <div class='next-course-response'>
      <strong>What you can take after {course_code}</strong>
      <div id="mini-graph"
           data-graph-type="next"
           style="width:380px;height:{height}px;border:1px solid #ddd;border-radius:8px;margin-top:6px;"
           data-graph='{graph_data}'></div>
            <p style='margin-top:8px;font-style:italic;color:#ffffff;'>
                Read this top-down: start from {course_code}, then follow the arrows to your immediate next options.
            </p>
      <script>document.dispatchEvent(new CustomEvent("renderCytoscapeGraph"));</script>
    </div>
    """


def respond_next_course_query(course_code: str, question: Optional[str] = None) -> str:
    """
    Respond to queries asking what courses come AFTER a given course —
    i.e., which courses list this one as a prerequisite.
    """
    if not course_code:
        return "Could you tell me which course you're referring to?"

    res = cypher_next_after(course_code)
    logger.debug(f"Next course query result for {course_code}: {res}")

    if not res or "error" in res[0]:
        return f"<p>I couldn't find any courses that list {course_code} as a prerequisite.</p>"

    formatted = [f"{r['code']} — {r.get('title', '')}" for r in res if r.get('code')]
    if not formatted:
        return f"<p>There are no courses that list {course_code} as a prerequisite.</p>"

    joined = (
        ", ".join(formatted[:-1]) + (f", and {formatted[-1]}" if len(formatted) > 1 else formatted[0])
    )

    factual_context = f"""
Course: {course_code}
Next possible courses (that require it):
{joined}
"""

    prompt = NEXT_COURSE_PROMPT.format(
        question=question or f'What can I take after {course_code}?',
        factual_context=factual_context,
        course_code=course_code
    )
    
    try:
        response = llm.invoke(prompt).strip()
    except Exception as e:
        logger.error(f"LLM error in next course query: {e}")
        response = ""

    if not response or len(response.split()) < 4:
        response = f"After completing **{course_code}**, you can take {joined} next."

    graph_html = render_next_course_graph(course_code, res)
    return f"""
    <div class='next-course-response'>
      {graph_html}
      <p style='margin-top:10px;'>{response}</p>
    </div>
    """
