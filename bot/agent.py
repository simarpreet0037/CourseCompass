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
        return f"{dept} {num}"

    return ""


def extract_first_json_object(text: str) -> Optional[str]:
    """Extract the first JSON object from text."""
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if not match:
        match = re.search(r"(\{[\s\S]*\})", text)
    return match.group(1) if match else None


def plan_from_llm(question: str) -> dict:
    """Use LLM to determine intent and extract course codes from question."""
    try:
        raw = llm.invoke(INTENT_PLAN_PROMPT.format(question=question)).strip()

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
    plan = plan_from_llm(question)
    intent = plan.get("intent", "general")
    course_codes = plan.get("course_codes", [])

    logger.info(f"Intent: {intent} | Codes: {course_codes} | Reason: {plan.get('reasoning', '')}")

    # Get first course code if available
    code = course_codes[0] if course_codes else None

    # Non-graph intents (plain text)
    if intent == "smalltalk":
        return {"type": "text", "content": respond_smalltalk(question)}
    
    if intent == "advising":
        return {"type": "text", "content": respond_advising(question)}
    
    if intent not in GRAPH_INTENTS:
        return {"type": "text", "content": respond_general(question)}

    # Graph-driven intents (HTML or enhanced text)
    if intent in {"prereq_query", "all_prerequisites"}:
        depth = 1 if intent == "prereq_query" else 5
        html = respond_prereq_query(code, question, depth=depth)
        return {"type": "html", "content": html}

    if intent == "next_course_query":
        response = respond_next_course_query(code, question)
        return {"type": "text", "content": response}

    if intent == "course_info":
        response = respond_course_info(question, code)
        return {"type": "text", "content": response}

    # Default fallback
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
        result = advisor_response(q)
        print("Bot:", result.get("content", ""))
