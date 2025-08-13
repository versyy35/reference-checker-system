from django.contrib import admin
from .models import Template, TextQuestion, MCQQuestion, RatingQuestion


class TextQuestionInline(admin.TabularInline):
    model = TextQuestion
    extra = 0
    fields = ['question_text', 'is_required', 'order_index', 'max_length', 'placeholder']


class MCQQuestionInline(admin.TabularInline):
    model = MCQQuestion
    extra = 0
    fields = ['question_text', 'is_required', 'order_index', 'options', 'allow_multiple']


class RatingQuestionInline(admin.TabularInline):
    model = RatingQuestion
    extra = 0
    fields = ['question_text', 'is_required', 'order_index', 'min_value', 'max_value', 'scale_label']


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_by', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'created_by']
    search_fields = ['title', 'description']
    list_editable = ['is_active']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Template Information', {
            'fields': ('title', 'description', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TextQuestionInline, MCQQuestionInline, RatingQuestionInline]
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TextQuestion)
class TextQuestionAdmin(admin.ModelAdmin):
    list_display = ['template', 'question_text_short', 'is_required', 'order_index']
    list_filter = ['template', 'is_required']
    search_fields = ['question_text']
    ordering = ['template', 'order_index']
    
    def question_text_short(self, obj):
        return obj.question_text[:50] + "..." if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = 'Question'


@admin.register(MCQQuestion)
class MCQQuestionAdmin(admin.ModelAdmin):
    list_display = ['template', 'question_text_short', 'is_required', 'allow_multiple', 'order_index']
    list_filter = ['template', 'is_required', 'allow_multiple']
    search_fields = ['question_text']
    ordering = ['template', 'order_index']
    
    def question_text_short(self, obj):
        return obj.question_text[:50] + "..." if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = 'Question'


@admin.register(RatingQuestion)
class RatingQuestionAdmin(admin.ModelAdmin):
    list_display = ['template', 'question_text_short', 'is_required', 'rating_range', 'order_index']
    list_filter = ['template', 'is_required']
    search_fields = ['question_text']
    ordering = ['template', 'order_index']
    
    def question_text_short(self, obj):
        return obj.question_text[:50] + "..." if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = 'Question'
    
    def rating_range(self, obj):
        return f"{obj.min_value} - {obj.max_value}"
    rating_range.short_description = 'Range'