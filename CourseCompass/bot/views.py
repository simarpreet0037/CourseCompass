from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.utils.safestring import mark_safe
from .agent import advisor_response


def chat_page(request):
    """
    Renders the main chat interface page (static layout with HTMX form).
    """
    return render(request, 'bot/chat.html')


@require_POST
def send_message(request):
    """
    Handles chat messages and renders appropriate response (text or HTML).
    """
    user_message = request.POST.get('message', '').strip()
    if not user_message:
        return HttpResponse('')

    bot_result = advisor_response(user_message)

    # Process result (dict or text)
    if isinstance(bot_result, dict):
        response_type = bot_result.get("type", "text")
        content = bot_result.get("content", "")
        if response_type == "html":
            bot_response = mark_safe(content)
        else:
            bot_response = content
    else:
        bot_response = str(bot_result)

    context = {
        "user_message": user_message,
        "bot_response": bot_response,
    }

    return render(request, "bot/chat_messages.html", context)