import re

from django.template.loader import render_to_string
from google.genai import types


def generate(client, model_id, system_instruction, history, prompt):
    """
    Generates Graphviz DOT code using Google GenAI.
    """
    # Ensure the system instruction explicitly requests DOT syntax.
    # Example: "You are a Graphviz expert. Output only valid DOT syntax."

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
    pattern = r"```(?:dot|graphviz)?\s*(.*?)```"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    if match:
        content = match.group(1)
    return content.strip()


def render(dot_code):
    """
    Renders DOT code into the HTML template using d3-graphviz logic.
    """
    return render_to_string(
        'diagrams/graphviz.html', {'dot_code': dot_code})
