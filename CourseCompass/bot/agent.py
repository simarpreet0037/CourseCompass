import os
import re
import json
from typing import List, Dict, Optional
from neo4j import GraphDatabase
from .groqllm import GroqLLM
from courses.neo4j_driver import driver

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
    "object oriented programming": "CS215",
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
    text = text.lower()
    for alias, code in COURSE_ALIASES.items():
        if alias in text:
            return code
    match = re.search(r"\b(cs|math|stat|eng|bio|chem)[\s\-]?(\d{3})\b", text)
    if match:
        return f"{match.group(1).upper()}{match.group(2)}"
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

def cypher_prereqs_for(code: str):
    query = """
    MATCH (target:Course {code:$code})-[:REQUIRES]->(g:PrerequisiteGroup)-[:HAS]->(p:Course)
    RETURN DISTINCT p.code AS code, p.title AS title, g.recommended AS recommended
    """
    return run_query(query, {"code": code})

def cypher_next_after(code: str):
    query = """
    MATCH (next:Course)-[:REQUIRES]->(:PrerequisiteGroup)-[:HAS]->(c:Course {code:$code})
    RETURN DISTINCT next.code AS code, next.title AS title
    """
    return run_query(query, {"code": code})

# ============================================================
# INTENT PLANNING (LLM)
# ============================================================
INTENT_PLAN_PROMPT = """You are a JSON-only planner for a university course advisor connected to a Neo4j graph.

Graph schema summary:
(Course)-[:REQUIRES]->(PrerequisiteGroup)-[:HAS]->(Course)
Course: code, title, credits, level, description
PrerequisiteGroup: type ("AND"/"OR"/"CUSTOM"), recommended (true/false/null)

Possible intents:
- prereq_query
- next_course_query
- course_info
- advising
- smalltalk
- general

Return ONLY valid JSON like:
{{"intent":"prereq_query","course_codes":["CS210"],"reasoning":"User asks what courses are required before CS210."}}

Question: "{question}"
"""

ALLOWED_INTENTS = {"prereq_query", "next_course_query", "course_info", "advising", "smalltalk", "general"}

def extract_first_json_object(text: str) -> Optional[str]:
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if not match:
        match = re.search(r"(\{[\s\S]*\})", text)
    return match.group(1) if match else None

def plan_from_llm(question: str) -> Dict:
    """Use LLM to interpret question into a structured plan."""
    try:
        raw = llm.invoke(INTENT_PLAN_PROMPT.format(question=question))
        json_str = extract_first_json_object(raw) or "{}"
        plan = json.loads(json_str)
    except Exception as e:
        print("[ERROR] Plan parsing failed:", e)
        plan = {}

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
    return llm.invoke(f"Respond warmly and politely to this greeting: {question}").strip()

def respond_general(question: str) -> str:
    """
    General intent: broader academic questions (not specific to one course).
    Provides full graph context in case the model wants to refer to real examples.
    """
    graph_context = summarize_graph_context(limit=40)
    prompt = f"""
You are a knowledgeable academic assistant who can answer general student questions.
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


# ============================================================
# GRAPH-BASED RESPONSE LOGIC
# ============================================================
def respond_prereq_query(course_code: str, question: Optional[str] = None) -> str:
    if not course_code:
        return "Could you tell me which course you're referring to?"

    res = cypher_prereqs_for(course_code)
    if not res or "error" in res[0]:
        return f"I couldn’t find any prerequisites for {course_code}."

    formatted = [f"{r['code']} — {r.get('title','')}" for r in res]
    joined = ", ".join(formatted[:-1]) + (f", and {formatted[-1]}" if len(formatted) > 1 else formatted[0])

    factual_context = f"""
Course: {course_code}
Prerequisites:
{joined}
"""

    prompt = f"""
You are an academic advisor explaining course requirements.
Student asked: "{question or f'What are the prerequisites for {course_code}?'}"

Here is what the database says:
{factual_context}

Now respond naturally and conversationally in 2–4 sentences.
Explain *why* these prerequisites might be required or what skills they prepare the student for.
Avoid sounding robotic; use an advisor’s tone.
"""
    response = llm.invoke(prompt).strip()
    if not response or len(response.split()) < 4:
        response = f"To take **{course_code}**, you’ll need to complete {joined} first."
    return response

def respond_next_course_query(course_code: str, question: Optional[str] = None) -> str:
    if not course_code:
        return "Which course have you completed so far?"

    res = cypher_next_after(course_code)
    if not res or "error" in res[0]:
        return f"I couldn’t find any courses that list {course_code} as a prerequisite."

    formatted = [f"{r['code']} — {r.get('title','')}" for r in res]
    joined = ", ".join(formatted[:-1]) + (f", and {formatted[-1]}" if len(formatted) > 1 else formatted[0])

    factual_context = f"""
Completed Course: {course_code}
Next Possible Courses:
{joined}
"""

    prompt = f"""
You are a friendly academic advisor helping a student plan their studies.
Student asked: "{question or f'What can I take after {course_code}?'}"

Here’s the factual information from the graph:
{factual_context}

Now respond conversationally in 2–4 sentences.
Summarize how these next courses build upon {course_code} and what kind of skills or knowledge the student will gain.
"""
    response = llm.invoke(prompt).strip()
    if not response or len(response.split()) < 4:
        response = f"After completing **{course_code}**, you can take {joined}."
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

    prereq_rows = cypher_prereqs_for(course_code)
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

def advisor_response(question: str) -> str:
    global conversation_history, last_course_code

    conversation_history.append({"role": "user", "content": question})
    plan = plan_from_llm(question)

    intent = plan.get("intent", "general")
    course_codes = plan.get("course_codes", []) or ([last_course_code] if last_course_code else [])
    if course_codes:
        last_course_code = course_codes[0]

    print("\n" + "=" * 80)
    print(f"[DEBUG] Intent: {intent} | Codes: {course_codes} | Reason: {plan.get('reasoning','')}")
    print("=" * 80 + "\n")

    # Graph-driven intents
    graph_intents = {"prereq_query", "next_course_query", "course_info"}

    if intent == "smalltalk":
        return respond_smalltalk(question)
    if intent == "advising":
        return respond_advising(question)
    if intent in graph_intents:
        code = course_codes[0] if course_codes else None
        if intent == "prereq_query":
            return respond_prereq_query(code)
        elif intent == "next_course_query":
            return respond_next_course_query(code)
        elif intent == "course_info":
            return respond_course_info(question, code)
    return respond_general(question)

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
