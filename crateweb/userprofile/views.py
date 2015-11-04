#!/usr/bin/env python3
# userprofile/views.py

from django.shortcuts import redirect, render
from .forms import UserProfileForm
from .models import get_or_create_user_profile


# =============================================================================
# User profile settings
# =============================================================================
# http://www.slideshare.net/pydanny/advanced-django-forms-usage
# ... e.g. slide 72

def edit_profile(request):
    profile = get_or_create_user_profile(request.user)
    form = UserProfileForm(request.POST or None, instance=profile)
    if form.is_valid():
        profile = form.save()
        profile.save()
        return redirect('home')
    return render(request, 'edit_profile.html',
                  {'form': form, 'profile': profile})
