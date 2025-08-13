from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q
from .models import Referee
from .forms import RefereeForm


class RefereeListView(LoginRequiredMixin, ListView):
    """
    Display list of all referees with search and filtering
    """
    model = Referee
    template_name = 'referees/list.html'
    context_object_name = 'referees'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Referee.objects.all().order_by('-created_at')
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(applicant_name__icontains=search_query) |
                Q(relationship__icontains=search_query)
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
        context['total_referees'] = Referee.objects.count()
        context['active_referees'] = Referee.objects.filter(is_active=True).count()
        context['inactive_referees'] = Referee.objects.filter(is_active=False).count()
        return context


class RefereeCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new referee in a modal window
    """
    model = Referee
    form_class = RefereeForm
    template_name = 'referees/create.html'
    success_url = reverse_lazy('referees:list')
    
    def form_valid(self, form):
        messages.success(self.request, f'✅ Referee "{form.cleaned_data["name"]}" added successfully!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, '❌ Please correct the errors below.')
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modal_mode'] = True
        return context


class RefereeUpdateView(LoginRequiredMixin, UpdateView):
    """
    Update an existing referee
    """
    model = Referee
    form_class = RefereeForm
    template_name = 'referees/edit.html'
    success_url = reverse_lazy('referees:list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Referee "{form.cleaned_data["name"]}" updated successfully!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class RefereeDetailView(LoginRequiredMixin, ListView):
    """
    Display referee details and their assigned forms
    """
    template_name = 'referees/detail.html'
    context_object_name = 'forms'
    
    def get_queryset(self):
        self.referee = get_object_or_404(Referee, pk=self.kwargs['pk'])
        return self.referee.form_set.all().order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['referee'] = self.referee
        return context


class RefereeDeleteView(LoginRequiredMixin, DeleteView):
    """
    Soft delete a referee (set is_active=False)
    """
    model = Referee
    template_name = 'referees/delete.html'
    success_url = reverse_lazy('referees:list')
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Soft delete - just set is_active to False
        self.object.is_active = False
        self.object.save()
        messages.success(request, f'Referee "{self.object.name}" has been deactivated.')
        return redirect(self.success_url)