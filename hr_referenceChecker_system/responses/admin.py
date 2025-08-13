from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponse
from .models import Response, Answer


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ['question_id', 'question_type', 'answer_value', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ['form_template', 'form_referee', 'submitted_at', 'answer_count', 'download_pdf']
    list_filter = ['submitted_at', 'form__template', 'form__status']
    search_fields = ['form__template__title', 'form__referee__name', 'form__referee__email']
    ordering = ['-submitted_at']
    readonly_fields = ['form', 'submitted_at', 'metadata']
    
    inlines = [AnswerInline]
    
    fieldsets = (
        ('Response Information', {
            'fields': ('form', 'submitted_at')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    def form_template(self, obj):
        return obj.form.template.title
    form_template.short_description = 'Template'
    form_template.admin_order_field = 'form__template__title'
    
    def form_referee(self, obj):
        return f"{obj.form.referee.name} ({obj.form.referee.email})"
    form_referee.short_description = 'Referee'
    form_referee.admin_order_field = 'form__referee__name'
    
    def answer_count(self, obj):
        return obj.answer_set.count()
    answer_count.short_description = 'Answers'
    
    def download_pdf(self, obj):
        return format_html(
            '<a href="/admin/responses/response/{}/export-pdf/" target="_blank">Download PDF</a>',
            obj.pk
        )
    download_pdf.short_description = 'Export'
    
    def has_add_permission(self, request):
        # Responses should only be created through form submissions
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of responses for audit purposes
        return request.user.is_superuser


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['response_info', 'question_id', 'question_type', 'answer_preview', 'created_at']
    list_filter = ['question_type', 'created_at']
    search_fields = ['response__form__referee__name', 'answer_value']
    ordering = ['-created_at']
    readonly_fields = ['response', 'question_id', 'question_type', 'answer_value', 'created_at']
    
    def response_info(self, obj):
        return f"{obj.response.form.template.title} - {obj.response.form.referee.name}"
    response_info.short_description = 'Response'
    
    def answer_preview(self, obj):
        return obj.answer_value[:100] + "..." if len(obj.answer_value) > 100 else obj.answer_value
    answer_preview.short_description = 'Answer'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser