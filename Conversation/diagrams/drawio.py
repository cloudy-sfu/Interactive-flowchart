import re
from xml.etree import ElementTree as ET
from django.template.loader import render_to_string
from google.genai import types


def generate(client, model_id, system_instruction, history, prompt):
    """
    Generates draw.io XML code using Google GenAI.
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
    
    # Extract XML from code blocks if present
    pattern = r"```(?:xml|drawio)?\s*(.*?)```"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    if match:
        content = match.group(1)
    
    return content.strip()


def extract_graph_model(xml_string):
    """
    Extracts the <mxGraphModel> content from a full <mxfile> XML string.
    Returns the original string if extraction fails or isn't needed.
    """
    try:
        # Strip potential whitespace
        xml_string = xml_string.strip()
        
        # Simple string-based check first to avoid parsing overhead if it's already a model
        if xml_string.startswith('<mxGraphModel'):
            return xml_string

        # Parse XML
        root = ET.fromstring(xml_string)
        
        # Handle standard .drawio / .xml format
        if root.tag == 'mxfile':
            # Look for the first diagram
            diagram = root.find('diagram')
            if diagram is not None:
                # Check if the content is inside mxGraphModel tag directly
                model = diagram.find('mxGraphModel')
                if model is not None:
                    return ET.tostring(model, encoding='unicode', method='xml')
                
                # Sometimes content is text (compressed), but our prompt usually asks for raw XML.
                # If it is text, we return it as is, the viewer handles compression.
                if diagram.text and diagram.text.strip():
                    return diagram.text.strip()

    except ET.ParseError:
        # If XML parsing fails, return original string as fallback
        # (The viewer has its own robust parser)
        pass
    except Exception as e:
        print(f"Error extracting drawio model: {e}")

    return xml_string


def render(drawio_xml):
    """
    Renders draw.io XML into the HTML template.
    """
    if not drawio_xml:
        return ""
    
    # Extract just the graph model part to ensure cleanest rendering
    clean_xml = extract_graph_model(drawio_xml)
    
    return render_to_string('diagrams/drawio.html', {'drawio_xml': clean_xml})
