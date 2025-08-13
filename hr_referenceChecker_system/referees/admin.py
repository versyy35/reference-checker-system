from django.contrib import admin
from .models import Referee


@admin.register(Referee)
class RefereeAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'applicant_name', 'relationship', 'is_active', 'created_at']
    list_filter = ['is_active', 'relationship', 'created_at']
    search_fields = ['name', 'email', 'applicant_name']
    list_editable = ['is_active']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Referee Information', {
            'fields': ('name', 'email', 'phone')
        }),
        ('Application Details', {
            'fields': ('applicant_name', 'relationship')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    readonly_fields = ['created_at']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return self.readonly_fields + ['created_at']
        return self.readonly_fields