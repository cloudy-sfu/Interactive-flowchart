from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.conversation_list, name='conversation_list'),
    path('create/', views.create_conversation, name='create_conversation'),
    path('detail/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('delete/<int:conversation_id>/', views.delete_conversation, name='delete_conversation'),
    path('chat_stream/<int:conversation_id>/', views.chat_stream, name='chat_stream'),
    path('generate_summary/<int:conversation_id>/', views.generate_summary, name='generate_summary'),
    path('create_diagram/<int:conversation_id>/', views.create_diagram, name='create_diagram'),
    path('diagram/<int:diagram_id>/', views.get_diagram_content, name='get_diagram_content'),
]
