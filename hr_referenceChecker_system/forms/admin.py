from django.contrib import admin
from django.utils.html import format_html
from .models import Form


@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    list_display = ['template', 'referee', 'status', 'access_link', 'created_at', 'submitted_at']
    list_filter = ['status', 'created_at', 'submitted_at']
    search_fields = ['template__title', 'referee__name', 'referee__email']
    ordering = ['-created_at']
    readonly_fields = ['unique_token', 'access_url', 'created_at', 'submitted_at']
    
    fieldsets = (
        ('Assignment Details', {
            'fields': ('template', 'referee', 'status')
        }),
        ('Access Information', {
            'fields': ('unique_token', 'access_url'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'submitted_at'),
            'classes': ('collapse',)
        }),
    )
    
    def access_link(self, obj):
        if obj.unique_token:
            url = obj.generate_access_url()
            return format_html('<a href="{}" target="_blank">Open Form</a>', url)
        return "No token"
    access_link.short_description = 'Access Link'
    
    def access_url(self, obj):
        if obj.unique_token:
            return obj.generate_access_url()
        return "Token will be generated on save"
    access_url.short_description = 'Full Access URL'
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of submitted forms
        if obj and obj.status == 'COMPLETED':
            return False
        return super().has_delete_permission(request, obj)