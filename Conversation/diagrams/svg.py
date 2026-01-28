import re
from django.template.loader import render_to_string
from google.genai import types


def generate(client, model_id, system_instruction, history, prompt):
    """
    Generates SVG code using Google GenAI.
    """
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

    # Regex to capture content inside ```svg, ```xml, or just generic code blocks.
    # It tries to find the opening <svg tag inside the block.
    pattern = r"```(?:svg|xml)?\s*(.*?)```"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    if match:
        content = match.group(1)
    return content.strip()


def render(svg_code):
    """
    Renders the SVG string into the HTML template.
    """
    if not svg_code:
        return ""

    return render_to_string('diagrams/svg.html', {'svg_code': svg_code})
