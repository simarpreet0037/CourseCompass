"""
Course info intent handler.
"""
import logging
import json
from typing import Optional

from ..queries import cypher_course_info, cypher_prereqs_full, cypher_next_after
from ..queries import cypher_neighborhood
from ..prompts import COURSE_INFO_PROMPT
from ..groqllm import GroqLLM
from ..config import API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

# Initialize LLM
llm = GroqLLM(api_key=API_KEY, model=MODEL_NAME)

def render_course_neighborhood(data: dict) -> str:
    """
    Render a neighbourhood graph: queried course in the centre,
    prerequisites flowing in from the top, follow-on courses below.
    graph-type='neighborhood' tells the JS renderer to apply the centre-pinned layout.
    """
    focus = data["focus"]
    prereq_codes = data["prereqs"]
    next_codes = data["next_courses"]

    if not focus.get("code"):
        return ""

    focus_code = focus["code"]
    nodes = [{"data": {"id": focus_code, "label": focus_code, "kind": "focus"}}]
    edges = []

    for code in prereq_codes:
        nodes.append({"data": {"id": code, "label": code, "kind": "prereq", "side": "prereq"}})
        edges.append({"data": {"id": f"{code}->{focus_code}", "source": code, "target": focus_code}})

    for code in next_codes:
        nodes.append({"data": {"id": code, "label": code, "kind": "next", "side": "next"}})
        edges.append({"data": {"id": f"{focus_code}->{code}", "source": focus_code, "target": code}})

    has_connections = bool(prereq_codes or next_codes)
    if not has_connections:
        return ""

    graph_data = json.dumps({"elements": {"nodes": nodes, "edges": edges}})
    prereq_label = f"Needs: {', '.join(prereq_codes)}" if prereq_codes else "No prerequisites"
    next_label   = f"Leads to: {', '.join(next_codes)}"  if next_codes  else "No follow-on courses"

    return f"""
    <div class='course-neighborhood'>
      <div id="mini-graph"
           data-graph-type="neighborhood"
           style="width:380px;height:260px;border:1px solid #ddd;border-radius:8px;margin-bottom:6px;"
           data-graph='{graph_data}'></div>
      <div style="font-size:0.75rem;color:#7a7a9a;display:flex;gap:1rem;flex-wrap:wrap;">
                <span>&#8593; {prereq_label}</span>
                <span>&#8595; {next_label}</span>
      </div>
            <p style='margin-top:8px;font-style:italic;color:#ffffff;'>
                This view centers the selected course so you can quickly see what feeds into it and what it unlocks next.
            </p>
      <script>document.dispatchEvent(new CustomEvent("renderCytoscapeGraph"));</script>
    </div>
    """

def respond_course_info(question: str, course_code: Optional[str]) -> str:
    """Respond to queries asking for detailed information about a course."""
    if not course_code:
        return "Could you specify which course you'd like to know more about?"

    rows = cypher_course_info(course_code)
    if not rows or "error" in rows[0]:
        return f"I couldn't find detailed information for {course_code}."

    c = rows[0]
    title = c.get("title", "Unknown Course")
    desc = c.get("description", "")
    level = c.get("level", "N/A")
    credits = c.get("credits", "N/A")

    neighborhood = cypher_neighborhood(course_code)
    prereqs      = neighborhood.get("prereqs", [])
    next_courses = neighborhood.get("next_courses", [])
    prereq_str   = ", ".join(prereqs)      if prereqs      else "None"
    next_str     = ", ".join(next_courses) if next_courses else "None"

    factual_context = f"""
Course Code: {course_code}
Title: {title}
Credits: {credits}
Level: {level}
Description: {desc or 'No description available.'}
Prerequisites: {prereq_str}
Next Courses: {next_str}
"""

    prompt = COURSE_INFO_PROMPT.format(question=question, factual_context=factual_context)
    
    try:
        response = llm.invoke(prompt).strip()
    except Exception as e:
        logger.error(f"LLM error in course info: {e}")
        response = ""

    if not response or len(response.split()) < 4:
        response = (
            f"**{course_code} — {title}** is a level {level} course worth {credits} credits.\n\n"
            f"{desc}\n\nPrerequisites: {prereq_str}. Next recommended courses: {next_str}."
        )
    graph_html = render_course_neighborhood(neighborhood)
    header = f"<strong>{course_code} — {title}</strong> &nbsp;·&nbsp; Level {level} &nbsp;·&nbsp; {credits} credits"

    return f"""
    <div class='course-info-response'>
      <p style='margin-bottom:8px;'>{header}</p>
      {graph_html}
      <p style='margin-top:8px;'>{response}</p>
    </div>
    """
