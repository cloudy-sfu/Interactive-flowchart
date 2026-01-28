from django.conf import settings
from django.test import TestCase
from Conversation.models import Diagram
import os
import yaml


class DiagramSyntaxConsistencyTest(TestCase):
    def test_syntax_consistency(self):
        # Path references
        base_dir = settings.BASE_DIR
        yaml_path = os.path.join(base_dir, 'Conversation', 'system_instruction.yaml')
        templates_dir = os.path.join(base_dir, 'templates', 'diagrams')
        diagrams_module_dir = os.path.join(base_dir, 'Conversation', 'diagrams')

        # Load system_instruction.yaml
        self.assertTrue(os.path.exists(yaml_path), f"system_instruction.yaml not found at {yaml_path}")
        with open(yaml_path, 'r', encoding='utf-8') as f:
            system_instruction = yaml.safe_load(f)

        diagram_instructions = system_instruction.get('diagram', {})
        self.assertIsInstance(diagram_instructions, dict, "'diagram' key in system_instruction.yaml must be a dictionary")

        # Iterate through all SyntaxChoice options
        for choice in Diagram.SyntaxChoice:
            syntax_label = choice.label  # e.g., 'mermaid'
            # choice itself works as the key for file_name_suffix if defined using the enum members or values

            # 1. Check correspondence in file_name_suffix
            self.assertIn(choice, Diagram.file_name_suffix,
                          f"Syntax '{syntax_label}' ({choice}) is missing from Diagram.file_name_suffix keys")

            # 2. Check key in system_instruction.yaml (diagram > syntax_name)
            self.assertIn(syntax_label, diagram_instructions,
                          f"Syntax '{syntax_label}' is missing from 'diagram' section in system_instruction.yaml")

            # 3. Check corresponding file in templates/diagrams
            template_path = os.path.join(templates_dir, f"{syntax_label}.html")
            self.assertTrue(os.path.exists(template_path),
                            f"Template file '{syntax_label}.html' is missing in {templates_dir}")

            # 4. Check corresponding module in Conversation.diagrams
            module_path = os.path.join(diagrams_module_dir, f"{syntax_label}.py")
            self.assertTrue(os.path.exists(module_path),
                            f"Module file '{syntax_label}.py' is missing in {diagrams_module_dir}")
