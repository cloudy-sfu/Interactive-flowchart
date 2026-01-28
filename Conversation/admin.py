from django.contrib import admin
from .models import Conversation, Message, Diagram

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('owner', 'title', 'created_time', 'modified_time')
    list_filter = ('created_time',)
    search_fields = ('owner__username', 'title')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'role', 'function_call', 'created_time')
    list_filter = ('role', 'function_call', 'created_time')
    search_fields = ('content',)


@admin.register(Diagram)
class DiagramAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'syntax', 'created_time')
    list_filter = ('created_time', 'syntax')

