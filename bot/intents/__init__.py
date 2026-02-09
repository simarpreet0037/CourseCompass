"""
Intent handlers for the CourseCompass chatbot.
"""

from .prereqs import respond_prereq_query, render_prereq_graph
from .advising import respond_advising, respond_general
from .course_info import respond_course_info
from .smalltalk import respond_smalltalk
from .next_course import respond_next_course_query

__all__ = [
    'respond_prereq_query',
    'render_prereq_graph',
    'respond_advising',
    'respond_general',
    'respond_course_info',
    'respond_smalltalk',
    'respond_next_course_query',
]
