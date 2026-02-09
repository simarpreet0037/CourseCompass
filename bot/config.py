"""
Bot configuration and constants.
"""
import os

# ============================================================
# LLM CONFIGURATION
# ============================================================
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "llama-3.1-8b-instant"

# ============================================================
# COURSE ALIASES
# Maps common course names to their codes
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
# INTENT DEFINITIONS
# ============================================================
ALLOWED_INTENTS = {
    "prereq_query",
    "all_prerequisites",
    "next_course_query",
    "course_info",
    "advising",
    "smalltalk",
    "general"
}

# Graph-based intents that can output HTML
GRAPH_INTENTS = {"prereq_query", "all_prerequisites", "next_course_query", "course_info"}
