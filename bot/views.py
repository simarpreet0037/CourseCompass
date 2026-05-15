"""
Bot chat views with error handling, logging, and session-based conversation history.
"""
import logging
import time
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.utils.safestring import mark_safe
from django.conf import settings
from .agent import advisor_response

logger = logging.getLogger(__name__)

# Simple in-memory rate limiter (per session)
# In production, use Redis or similar
rate_limit_cache = {}


def is_rate_limited(session_key: str, limit: int = None) -> bool:
    """Check if the session is rate limited."""
    if limit is None:
        limit = getattr(settings, 'CHAT_RATE_LIMIT', 30)
    
    now = time.time()
    window_start = now - 60  # 1 minute window
    
    if session_key not in rate_limit_cache:
        rate_limit_cache[session_key] = []
    
    # Clean old entries
    rate_limit_cache[session_key] = [
        t for t in rate_limit_cache[session_key] if t > window_start
    ]
    
    if len(rate_limit_cache[session_key]) >= limit:
        return True
    
    rate_limit_cache[session_key].append(now)
    return False


def get_chat_history(request) -> list:
    """Get chat history from session."""
    if 'chat_history' not in request.session:
        request.session['chat_history'] = []
    return request.session['chat_history']


def add_to_chat_history(request, user_message: str, bot_response: str, bot_meta: dict = None) -> None:
    """Add a message exchange to the session chat history."""
    history = get_chat_history(request)
    history.append({
        'user': user_message,
        'bot': bot_response,
        'meta': bot_meta or {},
        'timestamp': time.time()
    })
    # Keep only last 50 messages
    if len(history) > 50:
        history = history[-50:]
    request.session['chat_history'] = history
    request.session.modified = True


def chat_page(request):
    """Renders the main chat interface page."""
    return render(request, 'bot/chat.html')


@require_POST
def send_message(request):
    """
    Handles chat messages with error handling and rate limiting.
    """
    user_message = request.POST.get('message', '').strip()
    if not user_message:
        return HttpResponse('')

    # Rate limiting
    session_key = request.session.session_key or 'anonymous'
    if is_rate_limited(session_key):
        logger.warning(f"Rate limit exceeded for session: {session_key}")
        return render(request, "bot/chat_messages.html", {
            "user_message": user_message,
            "bot_response": "You're sending messages too quickly. Please wait a moment.",
        })

    # Get conversation history for context
    history = get_chat_history(request)
    
    try:
        bot_result = advisor_response(user_message, session_history=history)
    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        bot_result = {
            "type": "text",
            "content": "I apologize, but I encountered an error processing your request. Please try again."
        }

    # Process result (dict or text)
    bot_meta = {}
    if isinstance(bot_result, dict):
        response_type = bot_result.get("type", "text")
        content = bot_result.get("content", "")
        bot_meta = bot_result.get("meta", {}) if isinstance(bot_result.get("meta", {}), dict) else {}
        if response_type == "html":
            bot_response = mark_safe(content)
        else:
            bot_response = content
    else:
        bot_response = str(bot_result)

    # Save to conversation history
    add_to_chat_history(request, user_message, str(bot_response), bot_meta=bot_meta)

    context = {
        "user_message": user_message,
        "bot_response": bot_response,
    }

    return render(request, "bot/chat_messages.html", context)


@require_POST
def clear_history(request):
    """Clear the conversation history for the current session."""
    request.session['chat_history'] = []
    request.session.modified = True
    logger.info(f"Chat history cleared for session: {request.session.session_key}")
    return HttpResponse('')