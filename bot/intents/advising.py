"""
Advising and general query intent handlers.
"""
import logging
import json

from ..queries import summarize_graph_context
from ..queries import cypher_courses_by_level
from ..prompts import GENERAL_PROMPT, ADVISING_PROMPT
from ..groqllm import GroqLLM
from ..config import API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

# Initialize LLM
llm = GroqLLM(api_key=API_KEY, model=MODEL_NAME)


def respond_general(question: str) -> str:
    """
    General intent: broader academic questions (not specific to one course).
    Provides full graph context in case the model wants to refer to real examples.
    """
    graph_context = summarize_graph_context(limit=40)
    prompt = GENERAL_PROMPT.format(question=question, graph_context=graph_context)
    
    try:
        return llm.invoke(prompt).strip()
    except Exception as e:
        logger.error(f"LLM error in general response: {e}")
        return "I apologize, but I'm having trouble processing your question right now. Please try again."


def respond_advising(question: str) -> str:
    """
    Advising intent: Student seeks course guidance or planning help.
    The LLM receives full graph context to reason over real course options.
    """
    graph_context = summarize_graph_context(limit=60)
    prompt = ADVISING_PROMPT.format(question=question, graph_context=graph_context)
    
    try:
        advice = llm.invoke(prompt).strip()
    except Exception as e:
        logger.error(f"LLM error in advising response: {e}")
        advice = "I apologize, but I'm having trouble with course recommendations right now. Please try again."

    roadmap_html = _render_degree_roadmap()
    return f"""
    <div class='advising-response'>
      {roadmap_html}
      <p style='margin-top:10px;'>{advice}</p>
    </div>
    """


def _render_degree_roadmap() -> str:
    """
    Build a degree-roadmap graph: all courses grouped by academic level,
    with prerequisite edges drawn between them.
    graph-type='roadmap' tells the JS renderer to apply level-based row positioning.
    """
    courses = cypher_courses_by_level(limit=60)
    if not courses:
        return ""

    nodes = []
    edges = []
    seen_codes = set()

    for course in courses:
        code = course.get("code")
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        nodes.append({
            "data": {
                "id": code,
                "label": code,
                "kind": "course",
                "level": course.get("level") or 100,
            }
        })

    for course in courses:
        code = course.get("code")
        if not code:
            continue
        for prereq in (course.get("prereq_codes") or []):
            if prereq and prereq in seen_codes:
                edges.append({
                    "data": {
                        "id": f"{prereq}->{code}",
                        "source": prereq,
                        "target": code,
                    }
                })

    unique_levels = sorted({c.get("level") or 100 for c in courses if c.get("code")})
    height = max(260, len(unique_levels) * 100 + 60)

    graph_data = json.dumps({"elements": {"nodes": nodes, "edges": edges}})
    return f"""
    <div class='advising-roadmap'>
      <strong>Degree Roadmap</strong>
      <div id="mini-graph"
           data-graph-type="roadmap"
           style="width:380px;height:{height}px;border:1px solid #ddd;border-radius:8px;margin-top:6px;"
           data-graph='{graph_data}'></div>
            <p style='margin-top:8px;font-style:italic;color:#ffffff;'>
                Courses are arranged by level from top to bottom, with arrows showing prerequisite flow.
            </p>
      <script>document.dispatchEvent(new CustomEvent("renderCytoscapeGraph"));</script>
    </div>
    """
