from django.contrib import admin
from django.utils.html import format_html
from .models import Template, Question


class QuestionInline(admin.TabularInline):
    """
    Inline admin for questions within template admin
    """
    model = Question
    extra = 1
    fields = ['order', 'question_text', 'question_type', 'is_required', 'choices', 'rating_scale']
    ordering = ['order']


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    """
    Admin interface for templates
    """
    list_display = ['title', 'questions_count', 'assigned_forms_count', 'status_badge', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['title', 'description']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [QuestionInline]
    
    fieldsets = (
        ('Template Information', {
            'fields': ('title', 'description', 'instructions', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def questions_count(self, obj):
        count = obj.get_questions_count()
        if count > 0:
            return format_html('<span class="badge badge-info">{}</span>', count)
        return format_html('<span class="text-muted">0</span>')
    questions_count.short_description = 'Questions'
    
    def assigned_forms_count(self, obj):
        count = obj.get_assigned_forms_count()
        if count > 0:
            return format_html('<span class="badge badge-warning">{}</span>', count)
        return format_html('<span class="text-muted">0</span>')
    assigned_forms_count.short_description = 'Assigned Forms'
    
    def status_badge(self, obj):
        if obj.is_active:
            return format_html('<span class="badge badge-success">Active</span>')
        return format_html('<span class="badge badge-secondary">Inactive</span>')
    status_badge.short_description = 'Status'
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of templates with assigned forms
        if obj and obj.get_assigned_forms_count() > 0:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """
    Admin interface for questions
    """
    list_display = ['template', 'order', 'question_text_short', 'question_type', 'is_required', 'created_at']
    list_filter = ['question_type', 'is_required', 'template__is_active', 'created_at']
    search_fields = ['question_text', 'template__title']
    ordering = ['template', 'order']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Question Details', {
            'fields': ('template', 'question_text', 'question_type', 'order', 'is_required')
        }),
        ('Question Options', {
            'fields': ('choices', 'rating_scale', 'rating_labels'),
            'description': 'Configure options for choice-based and rating questions'
        }),
        ('Additional Information', {
            'fields': ('help_text', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def question_text_short(self, obj):
        return obj.question_text[:50] + "..." if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = 'Question Text'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('template')