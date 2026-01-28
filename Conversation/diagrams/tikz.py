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
    pattern = r"```(?:tikz)?\s*(.*?)```"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    if match:
        content = match.group(1)
    return content.strip()


def render(tikz_code):
    """
    Cleans the TikZ code of LaTeX document wrappers before rendering.
    TikZJax adds its own wrappers, so passing them causes crashes.
    """
    if not tikz_code:
        return ""
    # 1. Remove \documentclass[...] { ... }
    # Matches \documentclass, optional brackets [...], and mandatory braces {...}
    tikz_code = re.sub(r'\\documentclass(?:\[[^\]]*\])?\{[^}]*\}', '', tikz_code)
    # 2. Remove \usepackage{tikz} and \usepackage{standalone} (redundant/conflicting)
    # Matches \usepackage, optional brackets, and specific package names
    tikz_code = re.sub(r'\\usepackage(?:\[[^\]]*\])?\{(?:tikz|standalone)\}', '', tikz_code)
    # 3. Remove \begin{document} and \end{document}
    tikz_code = re.sub(r'\\(?:begin|end)\{document\}', '', tikz_code)
    # 4. Cleanup extra whitespace left behind
    tikz_code = tikz_code.strip()
    return render_to_string('diagrams/tikz.html', {'tikz_code': tikz_code})