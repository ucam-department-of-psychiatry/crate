#!/usr/bin/env python

"""
crate_anon/crateweb/extra/admin.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**Extensions to Django admin site classes.**

"""

import logging
from typing import Any, Dict, List, Type

from django.contrib.admin import ModelAdmin
from django.contrib.admin.views.main import ChangeList
from django.forms import ModelForm
from django.http import HttpResponse
from django.http.request import HttpRequest
from django.utils.encoding import force_text
from django.utils.translation import ugettext

log = logging.getLogger(__name__)


# =============================================================================
# Action-restricted ModelAdmin classes
# =============================================================================

class ReadOnlyChangeList(ChangeList):
    """
    Variant of :class:`django.contrib.admin.views.main.ChangeList` that that
    changes the text for a read-only context.
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.is_popup:
            title = ugettext('Select %s')
        else:
            title = ugettext('Select %s to view')
        self.title = title % force_text(self.opts.verbose_name)


class ReadOnlyModelAdmin(ModelAdmin):
    """
    ModelAdmin that allows users to view ("change"), but not add/edit/delete.

    You also need to do this:

    .. code-block:: none

        my_admin_site.index_template = 'admin/viewchange_admin_index.html'

    ... to give a modified admin/index.html that says "View/change" not
    "Change".

    """
    # http://stackoverflow.com/questions/3068843/permission-to-view-but-not-to-change-django  # noqa
    # See also http://stackoverflow.com/questions/6680631/django-admin-separate-read-only-view-and-change-view  # noqa
    # django/contrib/admin/templates/admin/change_form.html
    # django/contrib/admin/templatetags/admin_modify.py
    # https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.ModelAdmin.change_view  # noqa

    # Remove the tickbox for deletion, and the top/bottom action bars:
    actions = None

    # When you drill down into a single object, use a custom template
    # that removes the 'save' buttons:
    change_form_template = 'admin/readonly_view_form.html'

    def has_add_permission(self, request: HttpRequest, obj=None) -> bool:
        # Don't let the user add objects.
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        # Don't let the user delete objects.
        return False

    # Don't remove has_change_permission, or you won't see anything.
    # def has_change_permission(self, request, obj=None):
    #     return False

    def save_model(self, request: HttpRequest, obj,
                   form: ModelForm, change: bool):
        # Return nothing to make sure user can't update any data
        pass

    # Make list say "Select [model] to view" not "... change"
    def get_changelist(self, request: HttpRequest, **kwargs) \
            -> Type[ChangeList]:
        return ReadOnlyChangeList

    # Make single object view say "View [model]", not "Change [model]"
    def change_view(self,
                    request: HttpRequest,
                    object_id: int,
                    form_url: str = '',
                    extra_context: Dict[str, Any] = None) -> HttpResponse:
        extra_context = extra_context or {}
        # noinspection PyProtectedMember
        extra_context["title"] = "View %s" % force_text(
            self.model._meta.verbose_name)
        return super().change_view(request, object_id, form_url,
                                   extra_context=extra_context)


class AddOnlyModelAdmin(ModelAdmin):
    """
    ModelAdmin that allows add, but not edit or delete.

    Optional extra class attribute: ``fields_for_viewing``.
    """
    actions = None

    # When you drill down into a single object, use a custom template
    # that removes the 'save' buttons:
    change_form_template = 'admin/readonly_view_form.html'

    # But keep the default for adding:
    add_form_template = 'admin/change_form.html'

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def get_changelist(self, request: HttpRequest, **kwargs) \
            -> Type[ChangeList]:
        return ReadOnlyChangeList

    # This is an add-but-not-edit class.
    # http://stackoverflow.com/questions/7860612/django-admin-make-field-editable-in-add-but-not-edit  # noqa
    def get_readonly_fields(self, request: HttpRequest, obj=None) -> List[str]:
        if obj:  # obj is not None, so this is an edit
            # self.__class__ is the derived class
            if hasattr(self.__class__, 'fields_for_viewing'):
                # noinspection PyUnresolvedReferences
                return self.__class__.fields_for_viewing
            elif hasattr(self.__class__, 'readonly_fields'):
                return self.__class__.readonly_fields
            else:
                return self.__class__.fields
        else:  # This is an addition
            return []

    def get_fields(self, request: HttpRequest, obj=None) -> List[str]:
        if obj:  # edit (view)
            if hasattr(self.__class__, 'fields_for_viewing'):
                # noinspection PyUnresolvedReferences
                return self.__class__.fields_for_viewing
        return self.__class__.fields

    # Make single object view say "View [model]", not "Change [model]"
    def change_view(self,
                    request: HttpRequest,
                    object_id: int,
                    form_url: str = '',
                    extra_context: Dict[str, Any] = None) -> HttpResponse:
        extra_context = extra_context or {}
        # noinspection PyProtectedMember
        extra_context["title"] = "View %s" % force_text(
            self.model._meta.verbose_name)
        return super().change_view(request, object_id, form_url,
                                   extra_context=extra_context)


class EditOnlyModelAdmin(ModelAdmin):
    """
    ModelAdmin that allows editing, but not add or delete.

    Designed for e.g. when you have a fixed set of PKs. In that situation,
    ensure the PK field is in ``readonly_fields``.
    """
    actions = None

    def has_add_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False


class EditOnceOnlyModelAdmin(ModelAdmin):
    """
    ModelAdmin that allows editing, but not add or delete.

    Designed for e.g. when you have a fixed set of PKs. In that situation,
    ensure the PK field is in ``readonly_fields``.
    """
    actions = None

    change_form_template = 'admin/edit_once_view_form.html'

    def has_add_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False


class AllStaffReadOnlyModelAdmin(ReadOnlyModelAdmin):
    """
    ReadOnlyModelAdmin that allows access to all staff, not just superusers.
    (No easy way to make this work via multiple inheritance.)
    """
    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_staff

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return request.user.is_staff
