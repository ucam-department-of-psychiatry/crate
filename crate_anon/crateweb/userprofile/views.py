#!/usr/bin/env python3
# userprofile/views.py

from django.shortcuts import redirect, render
from crate_anon.crateweb.userprofile.forms import UserProfileForm


# =============================================================================
# User profile settings
# =============================================================================
# http://www.slideshare.net/pydanny/advanced-django-forms-usage
# ... e.g. slide 72

def edit_profile(request):
    profile = request.user.profile
    form = UserProfileForm(request.POST if request.method == 'POST' else None,
                           instance=profile)
    if form.is_valid():
        profile = form.save()
        profile.save()
        return redirect('home')
    return render(request, 'edit_profile.html',
                  {'form': form, 'profile': profile})
