import importlib
import json

import yaml
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from google import genai
from google.genai import types

from UserConfig.models import UserKeyBind
from .models import Conversation, Message, Diagram

# Load system instructions
with open("Conversation/system_instruction.yaml") as f:
    system_instruction = yaml.safe_load(f)


@login_required(login_url='login')
def create_conversation(request):
    conversation = Conversation.objects.create(owner=request.user)
    return redirect('conversation_detail', conversation_id=conversation.id)


@login_required(login_url='login')
def conversation_list(request):
    conversations = Conversation.objects.filter(owner=request.user).order_by(
        '-created_time')
    return render(request, 'Conversation/conversation_list.html',
                  {'conversations': conversations})


@login_required(login_url='login')
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, owner=request.user)
    diagrams = conversation.diagrams.only('id', 'created_time').order_by('created_time')
    messages = conversation.messages.all().order_by('created_time')
    return render(request, 'Conversation/conversation_detail.html', {
        'conversation': conversation,
        'diagrams': diagrams,
        'messages': messages,
        'syntax_choices': Diagram.SyntaxChoice.choices,
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
        conversation = get_object_or_404(Conversation, id=conversation_id,
                                         owner=request.user)

        past_messages = conversation.messages.order_by('created_time')
        gemini_history = []
        for msg in past_messages:
            if msg.content:
                gemini_history.append({
                    "role": msg.get_role_display(),
                    "parts": [{"text": msg.content}]
                })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    try:
        user_key_bind = UserKeyBind.objects.get(user=request.user)
        if not user_key_bind.model_key:
            raise ValueError("No model key bound.")
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    if not user_key_bind.model_key:
        return JsonResponse({
            'error': 'No access to large language model resources. Please contact the '
                     'administrator.'
        }, status=400)
    model_key = user_key_bind.model_key
    client = genai.Client(api_key=model_key.model_api_key)

    try:
        chat = client.chats.create(
            model=model_key.model_id,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction['plan']
            ),
            history=gemini_history
        )
    except Exception as e:
        return JsonResponse({'error': f"Failed to initialize model: {e}"}, status=500)

    # Title generation
    if not conversation.title:
        try:
            title_chat = client.chats.create(
                model=model_key.quick_model_id,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction['conv_title']),
                history=[]
            )
            title_response = title_chat.send_message(user_message_content)
            if title_response.text:
                conversation.title = title_response.text.strip()
                conversation.save()
        except Exception:
            pass

    def event_stream():
        _ = client  # hold reference to prevent client being closed
        full_response = ""
        try:
            response = chat.send_message_stream(user_message_content)
        except Exception as e1:
            yield str(e1)
            return

        for chunk in response:
            try:
                text = chunk.text
                if text:
                    full_response += text
                    yield text
            except ValueError:
                yield "Content filtered."

        if full_response:
            Message.objects.create(conversation=conversation,
                                   role=Message.RoleChoices.USER,
                                   content=user_message_content)
            Message.objects.create(conversation=conversation,
                                   role=Message.RoleChoices.MODEL,
                                   content=full_response.strip())

    return StreamingHttpResponse(event_stream(), content_type='text/plain')


@login_required(login_url='login')
@require_POST
def generate_summary(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, owner=request.user)
    try:
        user_key_bind = UserKeyBind.objects.get(user=request.user)
        model_key = user_key_bind.model_key
        client = genai.Client(api_key=model_key.model_api_key)

        history_objs = conversation.messages.order_by('created_time')
        gemini_history = []
        for msg in history_objs:
            gemini_history.append({"role": "user" if msg.role == 'U' else "model",
                                   "parts": [{"text": msg.content}]})

        chat = client.chats.create(
            model=model_key.model_id,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction['summarize']),
            history=gemini_history
        )
        response = chat.send_message("Generate summary diagram description.")
        return JsonResponse({'summary': response.text})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='login')
@require_POST
def create_diagram(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, owner=request.user)
    profile = request.POST.get('profile')
    syntax_input = request.POST.get('syntax', Diagram.SyntaxChoice.mermaid)
    if not profile:
        return JsonResponse({'error': 'Diagram description is empty.'}, status=400)
    try:
        user_key_bind = UserKeyBind.objects.get(user=request.user)
        model_key = user_key_bind.model_key
        client = genai.Client(api_key=model_key.model_api_key)
        # Determinate Syntax
        try:
            syntax_choice = Diagram.SyntaxChoice(syntax_input)
        except ValueError:
            return JsonResponse(
                {'error': f'Invalid syntax choice: {syntax_input}'}, status=400)
        try:
            renderer_name = syntax_choice.name
            renderer_module = importlib.import_module(
                f'.diagrams.{renderer_name}', package=__package__)
            instruction_text = system_instruction['diagram'][renderer_name]
        except (ModuleNotFoundError, KeyError):
            return JsonResponse({
                'error': f'Renderer not implemented for syntax: {syntax_choice.name}'
            }, status=501)
        # RETRY LOOP
        max_retries = settings.CONFIG['draw_diagram_max_retries']
        history = []
        for attempt in range(max_retries):
            try:
                final_content = renderer_module.generate(
                    client,
                    model_key.model_id,
                    instruction_text,
                    history,
                    profile
                )
                break
            except Exception as e:
                history.append({"role": "user", "parts": [{
                    "text": f"Fix the previous error and regenerate the diagram. In the "
                            f"attempt {attempt + 1}, you encountered the following "
                            f"error. {e}"
                }]})
                return JsonResponse({'error': str(e)}, status=500)
        else:
            return JsonResponse(
                {'error': f"Failed to generate valid diagram after "
                          f"{max_retries} attempts."},
                status=500
            )
        diagram = Diagram.objects.create(
            conversation=conversation,
            profile=profile,
            syntax=syntax_choice,
            content=final_content
        )
        rendered_html = renderer_module.render(final_content)
        return JsonResponse({
            'status': 'success',
            'diagram': {
                'id': diagram.id,
                'content': rendered_html,
                'source_code': final_content,
                'file_name': diagram.file_name,
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='login')
def get_diagram_content(request, diagram_id):
    try:
        diagram = Diagram.objects.get(id=diagram_id, conversation__owner=request.user)
    except Diagram.DoesNotExist:
        return JsonResponse({'error': 'Diagram not found or access denied.'}, status=404)
    try:
        syntax_choice = Diagram.SyntaxChoice(diagram.syntax)
    except ValueError:
        return JsonResponse(
            {'error': f'Invalid diagram syntax: {diagram.syntax}'}, status=500)
    try:
        renderer_name = syntax_choice.name
        renderer_module = importlib.import_module(
            f'.diagrams.{renderer_name}', package=__package__)
    except (ModuleNotFoundError, AttributeError):
        return JsonResponse({
            'error': f'Renderer not implemented for syntax: {syntax_choice}'}, status=501)
    try:
        html = renderer_module.render(diagram.content)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({
            'id': diagram.id,
            'content': html,
            'source_code': diagram.content,
            'file_name': diagram.file_name,
        })
