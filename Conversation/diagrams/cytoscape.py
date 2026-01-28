import json
import re
from typing import List, TypedDict, Optional

from django.template.loader import render_to_string
from google.genai import types


# --- 1. Schema Definitions ---
class NodeStyle(TypedDict, total=False):
    shape: Optional[str]
    color: Optional[str]

class Node(TypedDict):
    id: str
    label: str
    type: str
    style: NodeStyle

class EdgeStyle(TypedDict, total=False):
    line_style: Optional[str]
    color: Optional[str]

class Edge(TypedDict):
    source: str
    target: str
    label: str
    style: EdgeStyle

class GraphSchema(TypedDict):
    title: str
    direction: str
    nodes: List[Node]
    edges: List[Edge]

# --- 2. Validator ---
VALID_SHAPES = {
    'rectangle', 'round-rectangle', 'ellipse', 'triangle', 'pentagon',
    'hexagon', 'octagon', 'diamond', 'vee', 'rhomboid', 'cylinder',
    'star', 'cut-rectangle', 'bottom-round-rectangle', 'concave-hexagon'
}
ICON_PATTERN = re.compile(r'^[a-z0-9_-]+$')

def validate_diagram_json(data):
    """
    Validates and normalizes the JSON structure for the diagram.
    """
    if not isinstance(data, dict):
        return False, "Root must be a JSON object."

    if 'nodes' not in data or not isinstance(data['nodes'], list):
        return False, "Missing 'nodes' list."

    node_ids = set()
    for i, node in enumerate(data['nodes']):
        if 'id' not in node:
            return False, f"Node {i} missing 'id'."
        node_ids.add(node['id'])

        # Normalize Style
        style = node.get('style', {})
        if not isinstance(style, dict):
            style = {}
            node['style'] = style

        # Normalize Shape
        shape = style.get('shape', 'rectangle')
        if not shape: shape = 'rectangle'

        shape = shape.lower()
        if shape in ['rect', 'box']: shape = 'rectangle'
        if shape == 'circle': shape = 'ellipse'
        if shape == 'database': shape = 'cylinder'

        if shape not in VALID_SHAPES:
            style['shape'] = 'round-rectangle'
        else:
            style['shape'] = shape

        # Normalize Icon (ensure it is a string or None)
        if 'icon' in style and style['icon']:
            if not isinstance(style['icon'], str):
                style['icon'] = None

    if 'edges' in data:
        for i, edge in enumerate(data['edges']):
            if edge['source'] not in node_ids:
                return False, f"Edge {i} source '{edge['source']}' missing."
            if edge['target'] not in node_ids:
                return False, f"Edge {i} target '{edge['target']}' missing."

    return True, None

# --- 3. Generator ---
def generate(client, model_id, system_instruction, history, prompt):
    chat = client.chats.create(
        model=model_id,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=GraphSchema
        ),
        history=history
    )

    response = chat.send_message(prompt)

    try:
        json_content = json.loads(response.text)
    except json.JSONDecodeError:
        raise Exception(f"The response is not valid JSON. Raw response: {response.text}")
    is_valid, validation_error = validate_diagram_json(json_content)
    if is_valid:
        return json.dumps(json_content)
    else:
        raise Exception(f"The format of response is invalid. Validation error: "
                        f"{validation_error} Raw response: {response.text}")


def render(json_content_str):
    """
    Parses JSON data and renders it using the cytoscape.html template.
    Uses render_to_string to return the HTML content.
    """
    try:
        if isinstance(json_content_str, str):
            data = json.loads(json_content_str)
        else:
            data = json_content_str
    except json.JSONDecodeError:
        raise Exception("Invalid JSON data.")
    # Pass the data as a dumped JSON object to the template context
    return render_to_string('diagrams/cytoscape.html', {
        'graph_data_json': json.dumps(data)
    })
