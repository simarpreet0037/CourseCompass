"""
Next course query intent handler.
"""
import logging
from typing import Optional

from ..queries import cypher_next_after
from ..prompts import NEXT_COURSE_PROMPT
from ..groqllm import GroqLLM
from ..config import API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

# Initialize LLM
llm = GroqLLM(api_key=API_KEY, model=MODEL_NAME)


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
        return f"I couldn't find any courses that require {course_code}."

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
    return response
