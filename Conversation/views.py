import json

from google import genai
import yaml
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from UserConfig.models import UserKeyBind
from .models import Conversation, Message, Diagram

with open("Conversation/system_instruction.yaml") as f:
    system_instruction = yaml.safe_load(f)


@login_required(login_url='login')
def create_conversation(request):
    conversation = Conversation.objects.create(owner=request.user)
    return redirect('conversation_detail', conversation_id=conversation.id)

@login_required(login_url='login')
def conversation_list(request):
    conversations = Conversation.objects.filter(owner=request.user).order_by('-created_time')
    return render(request, 'Conversation/conversation_list.html', {'conversations': conversations})

@login_required(login_url='login')
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, owner=request.user)
    diagrams = conversation.diagrams.all().order_by('created_time')
    messages = conversation.messages.all().order_by('created_time')
    return render(request, 'Conversation/conversation_detail.html', {
        'conversation': conversation,
        'diagrams': diagrams,
        'messages': messages
    })

@login_required(login_url='login')
def delete_conversation(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, owner=request.user)
    if request.method == 'POST':
        conversation.delete()
    return redirect('conversation_list')

@login_required(login_url='login')
@require_POST
def chat_stream(request, conversation_id):
    try:
        data = json.loads(request.body)
        raw_message = data.get('message')
        if not raw_message:
            return JsonResponse({'error': 'Empty message'}, status=400)

        user_message_content = raw_message.strip()

        conversation = get_object_or_404(Conversation, id=conversation_id, owner=request.user)
        # 2. Build History
        # Gemini expects history in specific format
        past_messages = conversation.messages.order_by('created_time')
        gemini_history = []
        for msg in past_messages:
            if msg.content: # Skip empty messages
                # Note: System messages are handled differently in Gemini usually (instruction),
                # but for chat history, simple mapping is often enough.

                gemini_history.append({
                    "role": msg.get_role_display(),
                    "parts": [{"text": msg.content}]
                })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    # 1. Get API Key
    try:
        user_key_bind = UserKeyBind.objects.get(user=request.user)
        if not user_key_bind.model_key:
            raise ValueError("No model key bound.")
        model_key = user_key_bind.model_key
    except UserKeyBind.DoesNotExist:
        return JsonResponse({
                                'error': 'No API key configuration found for user. Please contact your admin.'},
                            status=400)
    except ValueError:
        return JsonResponse(
            {'error': 'No model key bound to user. Please contact your admin.'},
            status=400)

    api_key = model_key.model_api_key
    model_id = model_key.model_id

    if not model_id:
        return JsonResponse(
            {'error': 'No model ID configured. Please contact your admin.'}, status=400)

    # 3. Initialize Model
    # Handle "Gemini 3 Pro" logic - presumably matching strings or just passing what is in DB
    try:
        client = genai.Client(api_key=api_key)
        chat = client.chats.create(
            model=model_id,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction['plan']
            ),
            history=gemini_history
        )
    except Exception as e:
         return JsonResponse({'error': f"Failed to initialize model: {e}"}, status=500)

    # Generate conversation title if not exists
    if not conversation.title:
        try:
            title_model_id = settings.CONFIG.get("conv_title_model_id")
            if title_model_id:
                title_chat = client.chats.create(
                    model=title_model_id,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=system_instruction['conv_title']
                    ),
                    history=[]
                )
                title_response = title_chat.send_message(user_message_content)
                if title_response.text:
                    conversation.title = title_response.text.strip()
                    conversation.save()
        except Exception:
            pass # Fail silently as requested

    def event_stream():
        full_response = ""

        # keep alive and prevent garbage collection
        # solve problem: Cannot send a request, as the client has been closed.
        _ = client

        try:
            response = chat.send_message_stream(user_message_content)
        except Exception as e1:
            response = []
            error_part = str(e1)
            full_response += error_part
            yield error_part

        for chunk in response:
            # chunk.text can raise error if blocked by safety settings
            try:
                text = chunk.text
                if text:
                    full_response += text
                    yield text
            except ValueError:
                # Likely safety filter
                error_msg = "Content filtered because of violating safety policy."
                full_response += error_msg
                yield error_msg

        if full_response:
            # 4. Save User Message (only if conversation succeeded)
            Message.objects.create(
                conversation=conversation,
                role=Message.RoleChoices.USER,
                content=user_message_content
            )

            # 5. Save AI Response
            Message.objects.create(
                conversation=conversation,
                role=Message.RoleChoices.MODEL,
                content=full_response.strip()
            )

    return StreamingHttpResponse(event_stream(), content_type='text/plain')


@login_required(login_url='login')
@require_POST
def generate_summary(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, owner=request.user)

    try:
        user_key_bind = UserKeyBind.objects.get(user=request.user)
        if not user_key_bind.model_key:
            raise ValueError("No model key bound")
        model_key = user_key_bind.model_key
    except (UserKeyBind.DoesNotExist, ValueError):
        return JsonResponse({'error': 'No API key configuration found for user.'}, status=400)

    api_key = model_key.model_api_key
    model_id = model_key.model_id

    if not model_id:
        return JsonResponse({'error': 'No model ID configured.'}, status=400)

    client = genai.Client(api_key=api_key)

    past_messages = conversation.messages.order_by('created_time')
    gemini_history = []
    for msg in past_messages:
        if msg.content:
            role = "user" if msg.role == Message.RoleChoices.USER else "model"
            gemini_history.append({
                "role": role,
                "parts": [{"text": msg.content}]
            })

    try:
        chat = client.chats.create(
            model=model_id,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction['summarize']
            ),
            history=gemini_history
        )
        response = chat.send_message("Please generate the summary diagram description based on our conversation history.")
        return JsonResponse({'summary': response.text})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def render_mermaid_html(mermaid_code):
    clean_code = mermaid_code.replace("```mermaid", "").replace("```", "").strip()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true }});
        </script>
        <style>
            body {{ margin: 0; padding: 0; overflow: hidden; background-color: white; }}
            .mermaid {{ display: flex; justify-content: center; }}
        </style>
    </head>
    <body style="overflow: auto;">
        <div class="mermaid">
        {clean_code}
        </div>
    </body>
    </html>
    """


@login_required(login_url='login')
@require_POST
def create_diagram(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, owner=request.user)
    profile = request.POST.get('profile')

    if not profile:
        return JsonResponse({'error': 'Profile description is empty.'}, status=400)

    try:
        user_key_bind = UserKeyBind.objects.get(user=request.user)
        if not user_key_bind.model_key:
            raise ValueError("No model key bound")
        model_key = user_key_bind.model_key

        api_key = model_key.model_api_key
        model_id = model_key.model_id

        if not model_id:
             raise ValueError("No model ID configured.")

        client = genai.Client(api_key=api_key)

        chat = client.chats.create(
            model=model_id,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction['draw']
            ),
            history=[]
        )

        response = chat.send_message(profile)
        content = render_mermaid_html(response.text)

        diagram = Diagram.objects.create(
            conversation=conversation,
            profile=profile,
            content=content
        )
        return JsonResponse({
            'status': 'success',
            'diagram': {
                'id': diagram.id,
                'content': content
            }
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)