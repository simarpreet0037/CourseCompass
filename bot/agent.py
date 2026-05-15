"""
Course Advisor Agent - Main orchestrator for the CourseCompass chatbot.

This module coordinates intent detection and response generation using:
- config.py: Configuration and constants
- queries.py: Neo4j database queries
- prompts.py: LLM prompt templates
- intents/: Intent-specific response handlers
"""
import re
import json
import logging
from typing import Optional, Dict, List

from .config import COURSE_ALIASES, ALLOWED_INTENTS, GRAPH_INTENTS, API_KEY, MODEL_NAME
from .groqllm import GroqLLM
from .prompts import INTENT_PLAN_PROMPT
from .intents import (
    respond_prereq_query,
    respond_advising,
    respond_general,
    respond_course_info,
    respond_smalltalk,
    respond_next_course_query,
)

logger = logging.getLogger(__name__)

# Initialize LLM
llm = GroqLLM(api_key=API_KEY, model=MODEL_NAME)

COURSE_CODE_PATTERN = re.compile(r"\b(cs|math|stat|eng|bio|chem)[\s\-]?(\d{3})\b", re.I)
FOLLOWUP_REFERENCE_PATTERN = re.compile(r"\b(it|its|they|them|those|these|that|this|above|previous|earlier|same|ones)\b", re.I)


# ============================================================
# UTILITY HELPERS
# ============================================================
def normalize_course_code(text: str) -> str:
    """
    Normalize course names or phrases into the graph's code format.
    For example, "data structures" → "CS210", "cs210" → "CS210", "CS 115" → "CS115"
    Removes spaces for consistent matching (e.g., "CS 115" and "CS115" both become "CS115")
    """
    text = text.lower().strip()

    # Map aliases first
    for alias, code in COURSE_ALIASES.items():
        if alias in text:
            # Remove spaces from the normalized code
            return re.sub(r"([a-z]+)(\d+)", r"\1\2", code.upper())

    # Match patterns like "cs210", "cs 210", "math103", "math 103", etc. and remove space
    match = re.search(r"\b(cs|math|stat|eng|bio|chem)[\s\-]?(\d{3})\b", text)
    if match:
        dept = match.group(1).upper()
        num = match.group(2)
        return f"{dept}{num}"

    return ""


def extract_course_codes(text: str) -> List[str]:
    """Extract normalized course codes from free text."""
    if not text:
        return []
    out = []
    for match in COURSE_CODE_PATTERN.finditer(text):
        dept = match.group(1).upper()
        num = match.group(2)
        out.append(f"{dept}{num}")
    # Preserve order while removing duplicates.
    seen = set()
    ordered = []
    for code in out:
        if code not in seen:
            seen.add(code)
            ordered.append(code)
    return ordered


def looks_contextual_followup(question: str) -> bool:
    """
    Generic detector for context-dependent follow-ups.
    This does not hardcode specific asks; it detects referential language and short carry-on turns.
    """
    q = (question or "").strip()
    if not q or extract_course_codes(q):
        return False

    words = q.split()
    if FOLLOWUP_REFERENCE_PATTERN.search(q):
        return True

    # Short questions without explicit entities are often contextual follow-ups.
    return len(words) <= 8 and q.endswith("?")


def infer_context_from_history(session_history: Optional[List[Dict[str, str]]]) -> Dict[str, Optional[object]]:
    """
    Infer the most recent course code and graph intent from chat history.
    This helps resolve referential follow-up prompts that omit course codes.
    """
    if not session_history:
        return {"course_codes": [], "intent": None}

    inferred_codes: List[str] = []
    inferred_intent = None

    for item in reversed(session_history):
        user_text = str(item.get("user", ""))
        bot_text = str(item.get("bot", ""))
        meta = item.get("meta", {}) if isinstance(item, dict) else {}

        if not inferred_codes and isinstance(meta, dict):
            meta_codes = meta.get("course_codes", [])
            if isinstance(meta_codes, list):
                inferred_codes = [str(c).upper() for c in meta_codes if c]

        if inferred_intent is None and isinstance(meta, dict):
            meta_intent = str(meta.get("intent", "")).strip().lower()
            if meta_intent in ALLOWED_INTENTS:
                inferred_intent = meta_intent

        if not inferred_codes:
            codes = extract_course_codes(user_text) + extract_course_codes(bot_text)
            if codes:
                inferred_codes = codes

        if inferred_intent is None:
            bot_lower = bot_text.lower()
            if "prereq-response" in bot_lower or "prerequisites for" in bot_lower:
                inferred_intent = "prereq_query"
            elif "next-course-response" in bot_lower or "what you can take after" in bot_lower:
                inferred_intent = "next_course_query"
            elif "course-info-response" in bot_lower:
                inferred_intent = "course_info"

        if inferred_codes and inferred_intent:
            break

    return {"course_codes": inferred_codes, "intent": inferred_intent}


def build_planner_history_context(session_history: Optional[List[Dict[str, str]]], max_turns: int = 6) -> str:
    """Build compact recent-turn context for intent planning."""
    if not session_history:
        return "None"

    tail = session_history[-max_turns:]
    lines = []

    for idx, item in enumerate(tail, start=1):
        user_text = " ".join(str(item.get("user", "")).split())[:220]
        meta = item.get("meta", {}) if isinstance(item, dict) else {}
        intent = "unknown"
        codes = []
        if isinstance(meta, dict):
            intent = str(meta.get("intent", "unknown"))
            meta_codes = meta.get("course_codes", [])
            if isinstance(meta_codes, list):
                codes = [str(c).upper() for c in meta_codes[:4] if c]

        lines.append(f"Turn {idx} user: {user_text}")
        lines.append(f"Turn {idx} bot_meta: intent={intent}; course_codes={','.join(codes) if codes else '-'}")

    return "\n".join(lines)


def extract_first_json_object(text: str) -> Optional[str]:
    """Extract the first JSON object from text."""
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if not match:
        match = re.search(r"(\{[\s\S]*\})", text)
    return match.group(1) if match else None


def plan_from_llm(question: str, session_history: Optional[List[Dict[str, str]]] = None) -> dict:
    """Use LLM to determine intent and extract course codes from question."""
    history_context = build_planner_history_context(session_history)
    try:
        raw = llm.invoke(INTENT_PLAN_PROMPT.format(question=question, history_context=history_context)).strip()

        cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.I).strip()
        cleaned = cleaned[cleaned.find("{"):] if "{" in cleaned else cleaned

        try:
            plan = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode failed: {e}")
            plan = {}
    except Exception as e:
        logger.error(f"Plan parsing failed: {e}")
        plan = {}
        raw = ""

    # Normalize intent
    intent = str(plan.get("intent", "general")).lower().strip()
    if intent not in ALLOWED_INTENTS:
        intent = "general"

    # Normalize course codes
    codes = plan.get("course_codes", [])
    if not isinstance(codes, list):
        codes = []
    normalized_codes = [normalize_course_code(c) or c for c in codes]

    return {
        "intent": intent,
        "course_codes": normalized_codes,
        "reasoning": plan.get("reasoning", ""),
    }


# ============================================================
# MAIN ENTRYPOINT
# ============================================================
def advisor_response(question: str, session_history: Optional[List[Dict[str, str]]] = None) -> Dict:
    """
    Main entry point for processing user questions.
    
    Args:
        question: The user's question
        session_history: Optional conversation history for context
        
    Returns:
        dict with 'type' ('text' or 'html') and 'content'
    """
    # Determine intent
    plan = plan_from_llm(question, session_history=session_history)
    intent = plan.get("intent", "general")
    course_codes = plan.get("course_codes", [])

    # Use conversational context to resolve follow-up references.
    context = infer_context_from_history(session_history)
    followup = looks_contextual_followup(question)

    if not course_codes:
        # Deterministic fallback before using history.
        direct_code = normalize_course_code(question)
        if direct_code:
            course_codes = [direct_code]

    context_codes = context.get("course_codes") or []
    if followup and not course_codes and context_codes:
        course_codes = context_codes

    if followup and intent in {"general", "advising"} and context.get("intent") in GRAPH_INTENTS:
        intent = context["intent"]

    logger.info(f"Intent: {intent} | Codes: {course_codes} | Reason: {plan.get('reasoning', '')}")

    # Get first course code if available
    code = course_codes[0] if course_codes else None

    # Non-graph intents (plain text)
    result_meta = {
        "intent": intent,
        "course_codes": course_codes,
    }

    if intent == "smalltalk":
        return {"type": "text", "content": respond_smalltalk(question), "meta": result_meta}
    
    if intent == "advising":
        return {"type": "html", "content": respond_advising(question), "meta": result_meta}
    
    if intent not in GRAPH_INTENTS:
        return {"type": "text", "content": respond_general(question), "meta": result_meta}

    # Graph-driven intents (HTML or enhanced text)
    if intent in {"prereq_query", "all_prerequisites"}:
        # Use maximum safe traversal depth so indirect prerequisite chains are visible.
        depth = 8
        html = respond_prereq_query(code, question, depth=depth)
        return {"type": "html", "content": html, "meta": result_meta}

    if intent == "next_course_query":
        html = respond_next_course_query(code, question)
        return {"type": "html", "content": html, "meta": result_meta}

    if intent == "course_info":
        html = respond_course_info(question, code)
        return {"type": "html", "content": html, "meta": result_meta}

    # Default fallback
    return {"type": "text", "content": respond_general(question), "meta": result_meta}


# ============================================================
# CLI TESTING
# ============================================================
if __name__ == "__main__":
    print("Course Advisor ready! Type 'exit' to quit.")
    while True:
        q = input("You: ")
        if q.lower() in {"exit", "quit"}:
            break
        result = advisor_response(q)
        print("Bot:", result.get("content", ""))
