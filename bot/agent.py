import os
import re
import json
from typing import List, Dict, Optional
from .groqllm import GroqLLM
from CourseCompass.neo4j_driver import driver

# ============================================================
# CONFIGURATION
# ============================================================
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "llama-3.1-8b-instant"
llm = GroqLLM(api_key=API_KEY, model=MODEL_NAME)

# ============================================================
# COURSE ALIASES
# ============================================================
COURSE_ALIASES = {
    "data structures": "CS210",
    "data structures and algorithms": "CS210",
    "intro to programming": "CS110",
    "introduction to programming": "CS110",
    "object oriented programming": "CS115",
    "web programming": "CS215",
    "web and database programming": "CS215",
    "applied calculus i": "MATH103",
    "calculus 1": "MATH103",
    "calculus i": "MATH103",
}

# ============================================================
# UTILITY HELPERS
# ============================================================
def normalize_course_code(text: str) -> str:
    """
    Normalize course names or phrases into the graph's code format.
    For example, "data structures" → "CS 210", "cs210" → "CS 210"
    """
    text = text.lower().strip()

    # Map aliases first
    for alias, code in COURSE_ALIASES.items():
        if alias in text:
            # Insert a space after department letters if missing
            return re.sub(r"([a-z]+)(\d+)", r"\1 \2", code.upper())

    # Match patterns like "cs210", "math103", etc. and insert space
    match = re.search(r"\b(cs|math|stat|eng|bio|chem)[\s\-]?(\d{3})\b", text)
    if match:
        dept = match.group(1).upper()
        num = match.group(2)
        return f"{dept} {num}"  # ✅ space added here

    return ""



def run_query(query: str, params: Optional[dict] = None) -> List[Dict]:
    try:
        with driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]
    except Exception as e:
        return [{"error": str(e)}]

# ============================================================
# GRAPH QUERIES
# ============================================================
def cypher_course_info(code: str):
    query = """
    MATCH (c:Course {code:$code})
    RETURN c.code AS code, c.title AS title, c.credits AS credits,
           c.level AS level, c.description AS description
    """
    return run_query(query, {"code": code})

def cypher_prereqs_full(code: str, depth: int = 3):
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



def cypher_next_after(code: str):
    query = """
    MATCH (next:Course)-[:REQUIRES]->(:PrerequisiteGroup)-[:HAS]->(c:Course {code:$code})
    RETURN DISTINCT next.code AS code, next.title AS title
    """
    return run_query(query, {"code": code})

# ============================================================
# INTENT PLANNING (LLM)
# ============================================================
INTENT_PLAN_PROMPT = """
You are a structured planner for a University Course Advisor chatbot that is connected to a Neo4j graph database.

Your sole task is to analyze the student's question and return a *single JSON object* describing what kind of query or response is needed.

DO NOT include code fences, markdown, explanations, or extra text — only return one valid JSON object.

---

### Graph Schema (for your understanding)
(Course)-[:REQUIRES]->(PrerequisiteGroup)-[:HAS]->(Course)
Course node fields: code, title, credits, level, description  
PrerequisiteGroup node fields: type ("AND", "OR", "CUSTOM"), recommended (true/false/null)

---

### Possible Intents
| Intent | Description | Example Questions |
|--------|--------------|------------------|
| **prereq_query** | Student wants *direct* prerequisites of a course (1 level deep). | "What are the prerequisites for CS210?" / "Which courses are required before CS215?" |
| **all_prerequisites** | Student asks for *all* courses required before another course (recursively). | "What do I need before I can take CS340?" / "List all courses leading up to CS330." |
| **next_course_query** | Student wants to know what comes *after* a course. | "What can I take after CS110?" / "Which courses require CS210?" |
| **course_info** | Student asks for detailed info about one course. | "Tell me about CS215." / "What is CS110 about?" |
| **advising** | Student wants help planning or choosing courses. | "Which courses should I take next term?" / "Can you help me plan my degree?" |
| **smalltalk** | Greetings, thanks, or casual conversation. | "Hi there!" / "Thanks for your help." |
| **general** | Any other question not clearly tied to a course or advising topic. | "Who founded the university?" / "When does the semester start?" |

---

### Output Format
Return **only** valid JSON in this format:

{{
  "intent": "<one_of_the_intents_above>",
  "course_codes": ["<COURSE CODE(S) if mentioned, else empty list>"],
  "reasoning": "<brief explanation for why you chose this intent>"
}}

If you are uncertain, default to the "general" intent.

---

### Example Outputs

Q: "What are the prerequisites for CS210?"  
→ {{
  "intent": "prereq_query",
  "course_codes": ["CS210"],
  "reasoning": "User asks for the direct prerequisites of CS210."
}}

Q: "What do I need before I can take CS340?"  
→ {{
  "intent": "all_prerequisites",
  "course_codes": ["CS340"],
  "reasoning": "User asks for the full chain of prerequisite courses leading up to CS340."
}}

Q: "Can you help me pick my courses for next term?"  
→ {{
  "intent": "advising",
  "course_codes": [],
  "reasoning": "User requests personalized academic planning help."
}}

Q: "Hello there!"  
→ {{
  "intent": "smalltalk",
  "course_codes": [],
  "reasoning": "User is greeting the assistant."
}}

---

Question: "{question}"
"""



ALLOWED_INTENTS = {
    "prereq_query",
    "all_prerequisites",
    "next_course_query",
    "course_info",
    "advising",
    "smalltalk",
    "general"
}

def extract_first_json_object(text: str) -> Optional[str]:
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if not match:
        match = re.search(r"(\{[\s\S]*\})", text)
    return match.group(1) if match else None

def plan_from_llm(question: str) -> dict:
    try:
        raw = llm.invoke(INTENT_PLAN_PROMPT.format(question=question)).strip()

        cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.I).strip()
        cleaned = cleaned[cleaned.find("{"):] if "{" in cleaned else cleaned

        try:
            plan = json.loads(cleaned)
        except Exception as e:
            print("[ERROR] JSON decode failed:")
            plan = {}
    except Exception as e:
        print("[ERROR] Plan parsing failed completely:")
        plan = {}

    # normalize as before …
    intent = str(plan.get("intent", "general")).lower().strip()
    if intent not in ALLOWED_INTENTS:
        intent = "general"

    codes = plan.get("course_codes", [])
    if not isinstance(codes, list):
        codes = []
    normalized_codes = [normalize_course_code(c) or c for c in codes]

    return {
        "intent": intent,
        "course_codes": normalized_codes,
        "reasoning": plan.get("reasoning", ""),
        "raw_model": raw if 'raw' in locals() else ""
    }

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
        return f"(graph context unavailable: {e})"
# ============================================================
# RESPONSE HANDLERS
# ============================================================
def respond_smalltalk(question: str) -> str:
    return llm.invoke(f"Respond warmly and politely to this greeting, you are a helpfull University adadmic advisor call CourseCompass: {question}").strip()

def respond_general(question: str) -> str:
    """
    General intent: broader academic questions (not specific to one course).
    Provides full graph context in case the model wants to refer to real examples.
    """
    graph_context = summarize_graph_context(limit=40)
    prompt = f"""
You are a knowledgeable academic assistant called CourseCompass who can answer general student questions.
Use the context below only if it helps; otherwise, answer using your own understanding.
Stay concise (2–4 sentences) and conversational. Use the description of courses if relevant.

Student's question: "{question}"

University Course Graph (for reference) but do not mention that you use this graph:
{graph_context}

Assistant:
"""
    return llm.invoke(prompt).strip()


def respond_advising(question: str) -> str:
    """
    Advising intent: Student seeks course guidance or planning help.
    The LLM receives full graph context to reason over real course options.
    """
    graph_context = summarize_graph_context(limit=60)
    prompt = f"""
You are a friendly academic advisor at a university.
The student is asking for advice about which courses to take.
Use the provided course catalog below as real reference material, 
but only include details that are relevant to the question.
Keep your answer friendly, clear, and personalized (3–5 sentences).

Student's question: "{question}"

Course Catalog (context):
{graph_context}

Advisor:
"""
    return llm.invoke(prompt).strip()

import json

def render_prereq_graph(data: dict) -> str:
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

    # ✅ Cytoscape expects { elements: { nodes: [...], edges: [...] } }
    graph_data = json.dumps({
        "elements": {
            "nodes": nodes,
            "edges": edges
        }
    })

    # ✅ HTML structure unchanged (your other code still works)
    html = f"""
    <div class='prereq-response'>
      <strong>Prerequisites for {target["code"]}</strong><br>
      <div id="mini-graph"
           style="width:380px;height:260px;border:1px solid #ddd;border-radius:8px;"
           data-graph='{graph_data}'></div>
      <p style='margin-top:8px;font-style:italic;color:#374151;'>
        These courses prepare students for {target["code"]} by developing the necessary background knowledge.
      </p>
      <script>
        document.dispatchEvent(new CustomEvent("renderCytoscapeGraph"));
      </script>
    </div>
    """
    return html


# ============================================================
# GRAPH-BASED RESPONSE LOGIC
# ============================================================
def respond_prereq_query(course_code: str, question: Optional[str] = None, depth: int = 3) -> str:
    """
    Generate a factual prerequisite graph + very short summary.
    The graph is rendered directly from Neo4j data (no LLM),
    and the LLM only provides a concise description.
    """
    if not course_code:
        return "Could you tell me which course you're referring to?"

    # -------------------------------------------------------------
    # 1️⃣  Get full course + prereq info from Neo4j
    # -------------------------------------------------------------
    data = cypher_prereqs_full(course_code, depth)
    target = data.get("target", {})
    prereqs = data.get("prereqs", [])

    if not prereqs:
        return f"There are no prerequisites listed for {course_code}."

    # -------------------------------------------------------------
    # 2️⃣  Render visual graph (deterministic, no LLM)
    # -------------------------------------------------------------
    graph_html = render_prereq_graph(data)

    # -------------------------------------------------------------
    # 3️⃣  Ask LLM for one-sentence summary
    # -------------------------------------------------------------
    prereq_list = ", ".join([p["code"] for p in prereqs])
    prompt = f"""
You are an academic advisor.
Provide ONE short factual sentence (under 25 words)
summarizing how these courses prepare a student for {target.get('code','this course')} ({target.get('title','')}).

Do not restate the course codes.
Just describe the general skills or foundation gained.
"""
    summary = llm.invoke(prompt).strip()
    if not summary:
        summary = f"These prerequisites provide the essential background for {course_code}."

    # -------------------------------------------------------------
    # 4️⃣  Return ready-to-render HTML response
    # -------------------------------------------------------------
    return f"""
    <div class='prereq-response'>
      {graph_html}
      {summary}
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
    print("[DEBUG] Raw Cypher result:", res, flush=True)

    if not res or "error" in res[0]:
        return f"I couldn’t find any courses that require {course_code}."

    formatted = [f"{r['code']} — {r.get('title', '')}" for r in res if r.get('code')]
    if not formatted:
        return f"There are no courses that list {course_code} as a prerequisite."

    joined = (
        ", ".join(formatted[:-1]) + (f", and {formatted[-1]}" if len(formatted) > 1 else formatted[0])
    )

    factual_context = f"""
Course: {course_code}
Next possible courses (that require it):
{joined}
"""

    prompt = f"""
You are a helpful university academic advisor.
Student asked: "{question or f'What can I take after {course_code}?'}"

Here is what the database says:
{factual_context}

Respond conversationally in 2–4 sentences:
- Accurately reflect the factual context (these are the verified next courses).
- Briefly explain how these follow-up courses build on the knowledge from {course_code}.
- Keep the tone warm, helpful, and concise.
"""
    response = llm.invoke(prompt).strip()

    if not response or len(response.split()) < 4:
        response = f"After completing **{course_code}**, you can take {joined} next."
    return response

def respond_course_info(question: str, course_code: str) -> str:
    if not course_code:
        return "Could you specify which course you’d like to know more about?"

    rows = cypher_course_info(course_code)
    if not rows or "error" in rows[0]:
        return f"I couldn’t find detailed information for {course_code}."

    c = rows[0]
    title = c.get("title", "Unknown Course")
    desc = c.get("description", "")
    level = c.get("level", "N/A")
    credits = c.get("credits", "N/A")

    prereq_rows = cypher_prereqs_full(course_code)
    prereqs = [r["code"] for r in prereq_rows if "code" in r] if prereq_rows else []
    prereq_str = ", ".join(prereqs) if prereqs else "None"

    next_rows = cypher_next_after(course_code)
    next_courses = [r["code"] for r in next_rows if "code" in r] if next_rows else []
    next_str = ", ".join(next_courses) if next_courses else "None"

    factual_context = f"""
Course Code: {course_code}
Title: {title}
Credits: {credits}
Level: {level}
Description: {desc or 'No description available.'}
Prerequisites: {prereq_str}
Next Courses: {next_str}
"""

    prompt = f"""
You are a friendly university advisor.
A student asked: "{question}"

Here is the factual information from the university database:
{factual_context}

Now, summarize this naturally in a conversational tone (3–5 sentences).
If possible, mention what the course prepares students for or what comes next.
Avoid repeating the raw data directly; make it sound helpful and engaging.
"""
    response = llm.invoke(prompt).strip()

    if not response or len(response.split()) < 4:
        response = (
            f"**{course_code} — {title}** is a level {level} course worth {credits} credits.\n\n"
            f"{desc}\n\nPrerequisites: {prereq_str}. Next recommended courses: {next_str}."
        )
    return response

# ============================================================
# MAIN ENTRYPOINT
# ============================================================
conversation_history: List[Dict[str, str]] = []
last_course_code: Optional[str] = None

def advisor_response(question: str):
    global conversation_history, last_course_code

    conversation_history.append({"role": "user", "content": question})
    plan = plan_from_llm(question)

    intent = plan.get("intent", "general")
    course_codes = plan.get("course_codes", [])
    if course_codes:
        last_course_code = course_codes[0]

    print("\n" + "=" * 80)
    print(f"[DEBUG] Intent: {intent} | Codes: {course_codes} | Reason: {plan.get('reasoning','')}")
    print("=" * 80 + "\n")

    # Graph-based intents that can output HTML
    graph_intents = {"prereq_query", "all_prerequisites", "next_course_query", "course_info"}

    # ----------------------------------------------------------------------
    # 1️⃣  Non-graph intents (plain text)
    # ----------------------------------------------------------------------
    if intent == "smalltalk":
        return respond_smalltalk(question)
    if intent == "advising":
        return respond_advising(question)
    if intent not in graph_intents:
        return respond_general(question)

    # ----------------------------------------------------------------------
    # 2️⃣  Graph-driven intents (HTML or enhanced text)
    # ----------------------------------------------------------------------
    code = course_codes[0] if course_codes else None

    if intent in {"prereq_query", "all_prerequisites"}:
        depth = 1 if intent == "prereq_query" else 5
        html = respond_prereq_query(code, question, depth=depth)
        with open("example.txt", "w") as file:
            file.write(html)
        return {"type": "html", "content": html}

    elif intent == "next_course_query":
        # This one might remain text or later become graph too
        response = respond_next_course_query(code, question)
        return {"type": "text", "content": response}

    elif intent == "course_info":
        response = respond_course_info(question, code)
        return {"type": "text", "content": response}

    # Default fallback (safety net)
    return {"type": "text", "content": respond_general(question)}


# ============================================================
# CLI TESTING
# ============================================================
if __name__ == "__main__":
    print("Course Advisor ready! Type 'exit' to quit.")
    while True:
        q = input("You: ")
        if q.lower() in {"exit", "quit"}:
            break
        print("Bot:", advisor_response(q))
