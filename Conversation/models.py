from django.contrib.auth.models import User
from django.db import models

from UserConfig.models import ModelKey


class Conversation(models.Model):
    created_time = models.DateTimeField(auto_now_add=True)
    modified_time = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return self.title


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
    conversation = models.ForeignKey(
        Conversation, related_name='diagrams', on_delete=models.CASCADE)
    created_time = models.DateTimeField(auto_now_add=True)
    profile = models.TextField(blank=True)
    content = models.TextField(blank=True)
