from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Q
from django.db import transaction
from .models import Template, Question
from .forms import TemplateForm, QuestionForm, QuestionFormSet, TemplateSearchForm


class TemplateListView(LoginRequiredMixin, ListView):
    """
    Display list of all templates with search and filtering
    """
    model = Template
    template_name = 'formTemplates/list.html'  # Match your app folder pattern
    context_object_name = 'templates'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Template.objects.all().order_by('-created_at')
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filter by status
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['total_templates'] = Template.objects.count()
        context['active_templates'] = Template.objects.filter(is_active=True).count()
        context['inactive_templates'] = Template.objects.filter(is_active=False).count()
        return context


class TemplateCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new template with questions
    """
    model = Template
    form_class = TemplateForm
    template_name = 'formTemplates/create.html'  # Match your app folder pattern
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['question_formset'] = QuestionFormSet(self.request.POST, instance=self.object)
        else:
            context['question_formset'] = QuestionFormSet(instance=self.object)
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        question_formset = context['question_formset']
        
        # Debug: Print formset errors
        if not question_formset.is_valid():
            print("Formset errors:", question_formset.errors)
            print("Formset non-form errors:", question_formset.non_form_errors())
            for i, form_errors in enumerate(question_formset.errors):
                if form_errors:
                    print(f"Form {i} errors:", form_errors)
        
        # DON'T save the template yet - validate everything first
        with transaction.atomic():
            # Set the created_by field but don't save yet
            form.instance.created_by = self.request.user
            
            # Validate the question formset before saving anything
            if question_formset.is_valid():
                # Only now save the template
                self.object = form.save()
                question_formset.instance = self.object
                
                # Process choices_text for each question form
                for question_form in question_formset:
                    if question_form.cleaned_data and not question_form.cleaned_data.get('DELETE', False):
                        question_instance = question_form.save(commit=False)
                        question_instance.template = self.object
                        
                        # Handle choices_text
                        choices_text = question_form.cleaned_data.get('choices_text', '')
                        if choices_text and question_instance.question_type in ['SELECT', 'RADIO', 'CHECKBOX']:
                            question_instance.set_choices_from_text(choices_text)
                        
                        question_instance.save()
                
                valid_questions = len([f for f in question_formset if f.cleaned_data and not f.cleaned_data.get('DELETE', False)])
                messages.success(
                    self.request, 
                    f'✅ Template "{form.cleaned_data["title"]}" created successfully with {valid_questions} question(s)!'
                )
                return redirect('form_templates:list')
            else:
                # If questions are invalid, don't save the template at all
                messages.error(self.request, '❌ Please correct the errors in the questions below.')
                return self.form_invalid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, '❌ Please correct the errors below.')
        return super().form_invalid(form)


class TemplateUpdateView(LoginRequiredMixin, UpdateView):
    """
    Update an existing template and its questions
    """
    model = Template
    form_class = TemplateForm
    template_name = 'formTemplates/edit.html'  # Match your app folder pattern
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['question_formset'] = QuestionFormSet(self.request.POST, instance=self.object)
        else:
            context['question_formset'] = QuestionFormSet(instance=self.object)
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        question_formset = context['question_formset']
        
        with transaction.atomic():
            self.object = form.save()
            if question_formset.is_valid():
                question_formset.save()
                
                # Check if status changed
                if 'is_active' in form.changed_data:
                    status = "activated" if form.cleaned_data["is_active"] else "deactivated"
                    messages.success(self.request, f'✅ Template "{form.cleaned_data["title"]}" updated and {status}!')
                else:
                    messages.success(self.request, f'✅ Template "{form.cleaned_data["title"]}" updated successfully!')
                
                return redirect('form_templates:list')
            else:
                return self.form_invalid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, '❌ Please correct the errors below.')
        return super().form_invalid(form)


class TemplateDetailView(LoginRequiredMixin, DetailView):
    """
    Display template details and preview
    """
    model = Template
    template_name = 'formTemplates/detail.html'  # Match your app folder pattern
    context_object_name = 'template'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['questions'] = self.object.questions.all().order_by('order')
        context['assigned_forms_count'] = self.object.get_assigned_forms_count()
        return context


class TemplateDeleteView(LoginRequiredMixin, DeleteView):
    """
    Delete a template (with safety checks)
    """
    model = Template
    template_name = 'formTemplates/delete.html'  # Match your app folder pattern
    success_url = reverse_lazy('form_templates:list')
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        template_title = self.object.title
        
        # Check if template has assigned forms
        assigned_forms_count = self.object.get_assigned_forms_count()
        questions_count = self.object.get_questions_count()
        
        # Perform deletion
        self.object.delete()
        
        # Create appropriate success message
        if assigned_forms_count > 0:
            messages.success(
                request, 
                f'🗑️ Template "{template_title}" and {assigned_forms_count} assigned form(s) have been permanently deleted.'
            )
        else:
            messages.success(
                request, 
                f'🗑️ Template "{template_title}" with {questions_count} questions has been permanently deleted.'
            )
        
        return redirect(self.success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['assigned_forms_count'] = self.object.get_assigned_forms_count()
        context['questions_count'] = self.object.get_questions_count()
        return context


class TemplateDuplicateView(LoginRequiredMixin, DetailView):
    """
    Duplicate a template with all its questions
    """
    model = Template
    
    def post(self, request, *args, **kwargs):
        original_template = self.get_object()
        new_title = request.POST.get('new_title')
        
        if not new_title:
            new_title = f"{original_template.title} (Copy)"
        
        try:
            with transaction.atomic():
                new_template = original_template.duplicate(new_title, request.user)
                messages.success(
                    request,
                    f'✅ Template duplicated successfully as "{new_template.title}"!'
                )
                return redirect('form_templates:edit', pk=new_template.pk)
        except Exception as e:
            messages.error(request, f'❌ Error duplicating template: {str(e)}')
            return redirect('form_templates:detail', pk=original_template.pk)