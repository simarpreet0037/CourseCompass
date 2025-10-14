import os
import re
import json
from typing import List, Dict, Optional
from .groqllm import GroqLLM
from courses.neo4j_driver import driver

# ============================================================
# CONFIGURATION
# ============================================================
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "llama-3.1-8b-instant"
llm = GroqLLM(api_key=API_KEY, model=MODEL_NAME)

ALLOWED_INTENTS = {
    "prereq_query",
    "next_course_query",
    "course_info",
    "advising",
    "smalltalk",
    "general",
}

# ============================================================
# COURSE ALIASES (expand freely)
# ============================================================
COURSE_ALIASES = {
    "data structures": "CS210",
    "data structures and algorithms": "CS210",
    "intro to programming": "CS110",
    "introduction to programming": "CS110",
    "object oriented programming": "CS215",
    "web programming": "CS215",
    "web and database programming": "CS215",
    "applied calculus i": "MATH103",
    "calculus 1": "MATH103",
    "calculus i": "MATH103",
    "calculus": "MATH103",
}

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def normalize_course_code(text: str) -> str:
    """Convert aliases or text into standardized course codes."""
    text_l = text.lower()
    for alias, code in COURSE_ALIASES.items():
        if alias in text_l:
            return code
    m = re.search(r"\b(cs|math|stat|eng|bio|chem)[\s\-]?(\d{3})\b", text_l)
    if m:
        return f"{m.group(1).upper()}{m.group(2)}"
    return ""

def run_query(query: str, params: Optional[dict] = None) -> List[Dict]:
    """Run Cypher query with graceful error handling."""
    try:
        with driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]
    except Exception as e:
        return [{"error": str(e)}]

def extract_first_json_object(text: str) -> Optional[str]:
    """Extract the first JSON object (handles fenced or bare)."""
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1].strip()
    return None

def dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out

# ============================================================
# INTENT PLANNER PROMPT
# ============================================================
INTENT_PLAN_PROMPT = """You are a JSON-only planner for a university course advisor connected to a Neo4j graph.

Graph schema summary:
(Course)-[:REQUIRES]->(PrerequisiteGroup)-[:HAS]->(Course)
Course: code, title, credits, level, description
PrerequisiteGroup: type ("AND"/"OR"/"CUSTOM"), recommended (true/false/null)

Possible intents:
- prereq_query: asking what courses are needed before another course
- next_course_query: asking what courses can be taken after one
- course_info: asking for info about a course
- advising: general interest or suggestions (no database needed)
- smalltalk: greetings or thanks
- general: unrelated academic questions

Return ONLY a valid JSON object like:
{{"intent":"prereq_query","course_codes":["CS210"],"needs_graph":true,"reasoning":"User asks what is needed before CS210."}}

Question: "{question}"
"""

# ============================================================
# LLM REASONING + PARSING
# ============================================================
def plan_from_llm(question: str) -> Dict:
    """Ask LLM for intent classification, course detection, and reasoning."""
    raw = llm.invoke(INTENT_PLAN_PROMPT.format(question=question))

    json_str = extract_first_json_object(raw) or "{}"
    try:
        plan = json.loads(json_str)
    except Exception as e:
        plan = {"parse_error": str(e)}

    # --- Sanitize and guarantee defaults ---
    intent = str(plan.get("intent", "general")).lower().strip()
    if intent not in ALLOWED_INTENTS:
        intent = "general"

    codes = plan.get("course_codes", [])
    if not isinstance(codes, list):
        codes = []
    normalized = [normalize_course_code(str(c)) or str(c) for c in codes]
    normalized = dedupe_keep_order(normalized)

    needs_graph = bool(plan.get("needs_graph", intent in {"prereq_query", "next_course_query", "course_info"}))
    reasoning = str(plan.get("reasoning", "no reasoning")).strip()

    safe_plan = {
        "intent": intent,
        "course_codes": normalized,
        "needs_graph": needs_graph,
        "reasoning": reasoning,
        "raw_plan": plan,
        "raw_model": raw,
    }

    # --- Debug print ---
    print("[RAW MODEL OUTPUT]\n", raw, "\n")
    print("[PLAN]", json.dumps(safe_plan, indent=2))
    print(f"[DEBUG] Intent={intent} | Codes={normalized} | NeedsGraph={needs_graph} | Why={reasoning}")

    return safe_plan

# ============================================================
# GRAPH QUERY HELPERS
# ============================================================
def cypher_prereqs_for(code: str) -> List[Dict]:
    q = """
    MATCH (:Course {code:$code})-[:REQUIRES]->(g:PrerequisiteGroup)-[:HAS]->(p:Course)
    RETURN DISTINCT p.code AS code, p.title AS title, g.recommended AS recommended
    """
    return run_query(q, {"code": code})

def cypher_next_after(code: str) -> List[Dict]:
    q = """
    MATCH (next:Course)-[:REQUIRES]->(:PrerequisiteGroup)-[:HAS]->(c:Course {code:$code})
    RETURN DISTINCT next.code AS code, next.title AS title
    """
    return run_query(q, {"code": code})

def cypher_course_info(code: str) -> List[Dict]:
    q = """
    MATCH (c:Course {code:$code})
    RETURN c.code AS code, c.title AS title, c.credits AS credits,
           c.level AS level, c.description AS description
    """
    return run_query(q, {"code": code})

# ============================================================
# LLM-ONLY RESPONSES
# ============================================================
def llm_smalltalk(question: str) -> str:
    return llm.invoke(f"Respond warmly and briefly to this greeting or thanks: {question}").strip()

def llm_advising(question: str) -> str:
    prompt = f"""You are a friendly university course advisor.
Provide short, helpful course suggestions based on the student's interests.

Student: "{question}"
Advisor:"""
    return llm.invoke(prompt).strip()

def llm_general(question: str) -> str:
    prompt = f"""You are a concise academic assistant. 
Answer clearly and briefly:
{question}"""
    return llm.invoke(prompt).strip()

# ============================================================
# MAIN ENTRY POINT
# ============================================================
conversation_history: List[Dict[str, str]] = []
last_course_code: Optional[str] = None

def advisor_response(question: str) -> str:
    """Main entrypoint for Django and CLI."""
    global conversation_history, last_course_code

    conversation_history.append({"role": "user", "content": question})
    plan = plan_from_llm(question)

    intent = plan.get("intent", "general")
    course_codes = plan.get("course_codes", []) or ([last_course_code] if last_course_code else [])
    if course_codes:
        last_course_code = course_codes[0]

    # ------------- ROUTING -----------------
    if intent == "smalltalk":
        return llm_smalltalk(question)

    if intent == "advising":
        return llm_advising(question)

    if intent == "general" or not plan.get("needs_graph", False):
        return llm_general(question)

    if intent == "prereq_query":
        if not course_codes:
            return "Could you tell me which course you’re asking about?"
        target = course_codes[-1]
        rows = cypher_prereqs_for(target)
        if not rows or "error" in rows[0]:
            return f"I couldn’t find any prerequisites for {target}."
        bullets = [f"• {r['code']} – {r.get('title','')} ({'recommended' if r.get('recommended') else 'required'})" for r in rows]
        return f"The prerequisites for {target} are:\n" + "\n".join(bullets)

    if intent == "next_course_query":
        if not course_codes:
            return "Could you mention the course code?"
        base = course_codes[0]
        rows = cypher_next_after(base)
        if not rows or "error" in rows[0]:
            return f"No courses found that require {base} as a prerequisite."
        lines = [f"• {r['code']} – {r.get('title','')}" for r in rows]
        return f"After completing {base}, you can take:\n" + "\n".join(lines)

    if intent == "course_info":
        if not course_codes:
            return "Please mention which course you'd like to know about."
        code = course_codes[0]
        rows = cypher_course_info(code)
        if not rows or "error" in rows[0]:
            return f"I couldn’t find information for {code}."
        c = rows[0]
        desc = c.get("description", "No description available.")
        return f"📘 **{c['code']} – {c['title']}**\nLevel {c['level']} | {c['credits']} credits\n\n{desc}"

    # Fallback
    return llm_general(question)

# ============================================================
# LOCAL TESTING
# ============================================================
if __name__ == "__main__":
    print("Course Advisor ready! Type 'exit' to quit.")
    while True:
        q = input("You: ")
        if q.lower() in ("exit", "quit"):
            break
        print("Bot:", advisor_response(q))
