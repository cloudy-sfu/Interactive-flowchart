from django.contrib.auth.models import User
from django.db import models

from UserConfig.models import ModelKey


class Conversation(models.Model):
    created_time = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return self.title

    def modified_time(self):
        last_message = self.messages.order_by('created_time').last()
        if last_message:
            return last_message.created_time
        else:
            return None


class Message(models.Model):
    class RoleChoices(models.TextChoices):
        SYSTEM = 'S', 'system'
        USER = 'U', 'user'
        MODEL = 'M', 'model'
        TOOL = 'T', 'tool'

    class FunctionCallChoices(models.TextChoices):
        SUMMARIZE = 'S', 'Summarize'
        RENDER = 'R', 'Render'
        RETRIEVE = 'E', 'Retrieve'

    conversation = models.ForeignKey(
        Conversation, related_name='messages', on_delete=models.CASCADE)
    created_time = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=1, choices=RoleChoices.choices)
    content = models.TextField(blank=True)
    function_call = models.CharField(
        max_length=64, null=True, choices=FunctionCallChoices.choices)


class Diagram(models.Model):
    class SyntaxChoice(models.TextChoices):
        mermaid = 'MER', 'mermaid'
        cytoscape = 'CYT', 'cytoscape'
        graphviz = 'GVZ', 'graphviz'
        tikz = 'TIK', 'tikz'
        drawio = 'DRI', 'drawio'
        svg = 'SVG', 'svg'

    file_name_suffix = {
        SyntaxChoice.mermaid: "_mermaid.txt",
        SyntaxChoice.cytoscape: "_cytoscape.json",
        SyntaxChoice.graphviz: ".gv",
        SyntaxChoice.tikz: ".tikz",
        SyntaxChoice.drawio: ".drawio",
        SyntaxChoice.svg: ".svg",
    }

    conversation = models.ForeignKey(
        Conversation, related_name='diagrams', on_delete=models.CASCADE)
    created_time = models.DateTimeField(auto_now_add=True)
    profile = models.TextField(blank=True)
    syntax = models.CharField(
        max_length=3, choices=SyntaxChoice.choices, default=SyntaxChoice.mermaid)
    content = models.TextField(blank=True)

    @property
    def file_name(self):
        return f"diagram_{self.id}{self.file_name_suffix.get(self.syntax, '.txt')}"
