from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from .agent import advisor_response



def chat_page(request):
    """
    Renders the main chat interface page.
    """
    return render(request, 'bot/chat.html')

@require_POST
def send_message(request):
    """
    Handles the user's chat message submitted via POST (HTMX).
    Returns an HTML snippet containing the user message and the bot response.
    """

    print("Received POST request for send_message")
    user_message = request.POST.get('message', '').strip()

    # If the message is empty, return an empty response (do not update UI)
    if not user_message:
        return HttpResponse('')

    # Get the bot's response (replace this with real logic or an API call)
    bot_response = advisor_response(user_message)

    # Render only the chat message snippets (HTMX will insert this into the chat window)
    return render(request, 'bot/chat_messages.html', {
        'user_message': user_message,
        'bot_response': bot_response,
    })


