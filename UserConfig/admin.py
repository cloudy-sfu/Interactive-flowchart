from django.contrib import admin
from .models import ModelKey, UserKeyBind

# Register your models here.
class UserKeyBindInline(admin.TabularInline):
    model = UserKeyBind
    extra = 0
    autocomplete_fields = ['user']

@admin.register(ModelKey)
class ModelKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'model_provider')
    list_filter = ('model_provider',)
    search_fields = ('name', 'model_provider')
    inlines = [UserKeyBindInline]
