"""
Advising and general query intent handlers.
"""
import logging

from ..queries import summarize_graph_context
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
        return llm.invoke(prompt).strip()
    except Exception as e:
        logger.error(f"LLM error in advising response: {e}")
        return "I apologize, but I'm having trouble with course recommendations right now. Please try again."
