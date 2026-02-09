"""
Smalltalk intent handler.
"""
import logging

from ..prompts import SMALLTALK_PROMPT
from ..groqllm import GroqLLM
from ..config import API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

# Initialize LLM
llm = GroqLLM(api_key=API_KEY, model=MODEL_NAME)


def respond_smalltalk(question: str) -> str:
    """Respond to greetings and casual conversation."""
    prompt = SMALLTALK_PROMPT.format(question=question)
    
    try:
        return llm.invoke(prompt).strip()
    except Exception as e:
        logger.error(f"LLM error in smalltalk: {e}")
        return "Hello! I'm CourseCompass, your academic advisor. How can I help you today?"
