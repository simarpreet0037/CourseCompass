"""
Course info intent handler.
"""
import logging
from typing import Optional

from ..queries import cypher_course_info, cypher_prereqs_full, cypher_next_after
from ..prompts import COURSE_INFO_PROMPT
from ..groqllm import GroqLLM
from ..config import API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

# Initialize LLM
llm = GroqLLM(api_key=API_KEY, model=MODEL_NAME)


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

    prereq_data = cypher_prereqs_full(course_code)
    prereqs = [r["code"] for r in prereq_data.get("prereqs", []) if "code" in r]
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
    return response
