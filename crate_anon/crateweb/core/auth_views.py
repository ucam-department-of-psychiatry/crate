#!/usr/bin/env python3
# core/auth_views.py

import logging
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render

log = logging.getLogger(__name__)


def login_view(request):
    # don't call it login (name clash with django.contrib.auth.login)
    # https://www.fir3net.com/Web-Development/Django/django.html
    # http://www.flagonwiththedragon.com/2011/06/16/django-authenticationform-for-user-login/  # noqa
    # http://stackoverflow.com/questions/16750464/django-redirect-after-login-not-working-next-not-posting  # noqa

    nextpage = request.GET.get('next', reverse('home'))
    log.debug("login_view: nextpage: {}".format(nextpage))
    if request.user.is_authenticated():
        return HttpResponseRedirect(nextpage)
    form = AuthenticationForm(
        None, request.POST if request.method == 'POST' else None)
    if form.is_valid():
        # ... the form handles a bunch of user validation
        login(request, form.get_user())
        return HttpResponseRedirect(nextpage)
    return render(request, 'login.html', {'form': form, 'next': nextpage})


def logout_view(request):
    logout(request)
    return render(request, 'logged_out.html')


def password_change(request):
    # https://docs.djangoproject.com/en/1.8/topics/auth/default/#module-django.contrib.auth.forms  # noqa
    form = PasswordChangeForm(
        data=request.POST if request.method == 'POST' else None,
        user=request.user)
    if form.is_valid():
        form.save()
        update_session_auth_hash(request, form.user)
        # ... so the user isn't immediately logged out
        return redirect('home')
    return render(request, 'password_change.html', {'form': form})


# No password_reset function yet (would use PasswordResetForm)
# ... that's to reset forgotten passwords.
