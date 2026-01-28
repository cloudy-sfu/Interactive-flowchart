import re

from django.template.loader import render_to_string
from google.genai import types


def generate(client, model_id, system_instruction, history, prompt):
    chat = client.chats.create(
        model=model_id,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="text/plain"
        ),
        history=history
    )
    response = chat.send_message(prompt)
    content = response.text
    pattern = r"```(?:mermaid)?\s*(.*?)```"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    if match:
        content = match.group(1)
    return content.strip()


def render(mermaid_code):
    return render_to_string('diagrams/mermaid.html', {'mermaid_code': mermaid_code})
