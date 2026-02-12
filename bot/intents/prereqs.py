"""
Prerequisite query intent handlers.
"""
import json
import logging
from typing import Optional

from ..queries import cypher_prereqs_full
from ..prompts import PREREQ_SUMMARY_PROMPT
from ..groqllm import GroqLLM
from ..config import API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

# Initialize LLM
llm = GroqLLM(api_key=API_KEY, model=MODEL_NAME)


def render_prereq_graph(data: dict) -> str:
    """Render prerequisite graph as HTML with Cytoscape data."""
    target = data["target"]
    prereqs = data["prereqs"]

    # Build Cytoscape-compatible node and edge lists
    nodes = [{
        "data": {
            "id": target["code"],
            "label": target["code"],
            "kind": "target"
        }
    }]
    edges = []

    for p in prereqs:
        # Add node if not already present
        if not any(n["data"]["id"] == p["code"] for n in nodes):
            nodes.append({
                "data": {
                    "id": p["code"],
                    "label": p["code"],
                    "type": p.get("type", "CUSTOM"),
                    "recommended": bool(p.get("recommended", False))
                }
            })

        # Link prerequisite -> target
        edges.append({
            "data": {
                "id": f"{p['code']}->{target['code']}",
                "source": p["code"],
                "target": target["code"],
                "type": p.get("type", "CUSTOM")
            }
        })

    # Cytoscape expects { elements: { nodes: [...], edges: [...] } }
    graph_data = json.dumps({
        "elements": {
            "nodes": nodes,
            "edges": edges
        }
    })

    html = f"""
    <div class='prereq-response'>
      <strong>Prerequisites for {target["code"]}</strong><br>
      <div id="mini-graph"
           style="width:380px;height:260px;border:1px solid #ddd;border-radius:8px;"
           data-graph='{graph_data}'></div>
      <p style='margin-top:8px;font-style:italic;color:#ffffff;'>
        These courses prepare students for {target["code"]} by developing the necessary background knowledge.
      </p>
      <script>
        document.dispatchEvent(new CustomEvent("renderCytoscapeGraph"));
      </script>
    </div>
    """
    return html


def respond_prereq_query(course_code: str, question: Optional[str] = None, depth: int = 3) -> str:
    """
    Generate a factual prerequisite graph + very short summary.
    The graph is rendered directly from Neo4j data (no LLM),
    and the LLM only provides a concise description.
    """
    if not course_code:
        return "Could you tell me which course you're referring to?"

    # Get full course + prereq info from Neo4j
    data = cypher_prereqs_full(course_code, depth)
    target = data.get("target", {})
    prereqs = data.get("prereqs", [])

    if not prereqs:
        return f"There are no prerequisites listed for {course_code}."

    # Render visual graph (deterministic, no LLM)
    graph_html = render_prereq_graph(data)

    # Ask LLM for one-sentence summary
    prompt = PREREQ_SUMMARY_PROMPT.format(
        course_code=target.get('code', course_code),
        course_title=target.get('title', '')
    )
    
    try:
        summary = llm.invoke(prompt).strip()
    except Exception as e:
        logger.error(f"LLM error in prereq summary: {e}")
        summary = ""
    
    if not summary:
        summary = f"These prerequisites provide the essential background for {course_code}."

    # Return ready-to-render HTML response
    return f"""
    <div class='prereq-response'>
      {graph_html}
      {summary}
    </div>
    """
