# core/extra.py

# https://djangosnippets.org/snippets/2206/
# https://docs.djangoproject.com/en/1.8/ref/files/uploads/

import logging
logger = logging.getLogger(__name__)
import os
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.core.files.uploadedfile import UploadedFile
from django.db.models import FileField
from django import forms
from django.template.defaultfilters import filesizeformat
from django.utils.encoding import force_text
from django.utils.translation import ugettext, ugettext_lazy
from core.nhs import is_valid_nhs_number


# =============================================================================
# FileField handling
# =============================================================================

class ContentTypeRestrictedFileField(FileField):
    """
    Same as FileField, but you can specify:
        * content_types - list containing allowed content_types.
          Example: ['application/pdf', 'image/jpeg']
        * max_upload_size - a number indicating the maximum file size allowed
          for upload.
            2.5MB - 2621440
            5MB - 5242880
            10MB - 10485760
            20MB - 20971520
            50MB - 5242880
            100MB - 104857600
            250MB - 214958080
            500MB - 429916160
    """
    def __init__(self, *args, **kwargs):
        self.content_types = kwargs.pop("content_types", None)
        if self.content_types is None:
            self.content_types = []
        self.max_upload_size = kwargs.pop("max_upload_size", None)
        super().__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        data = super().clean(*args, **kwargs)
        # logger.debug("data: {}".format(repr(data)))
        f = data.file
        if not isinstance(f, UploadedFile):  # RNC
            # no new file uploaded; there won't be a content-type to check
            return data
        # logger.debug("f: {}".format(repr(f)))
        content_type = f.content_type
        if content_type not in self.content_types:
            raise forms.ValidationError(ugettext_lazy(
                'Filetype not supported.'))
        if self.max_upload_size is not None and f._size > self.max_upload_size:
            raise forms.ValidationError(ugettext_lazy(
                'Please keep filesize under %s. Current filesize %s')
                % (filesizeformat(self.max_upload_size),
                   filesizeformat(f._size)))
        return data


# http://stackoverflow.com/questions/16041232/django-delete-filefield
# These two auto-delete files from filesystem when they are unneeded:
# ... with a bit of modification to make them generic (RNC)
# Attach them with signals; see e.g. Study model.
def auto_delete_files_on_instance_delete(instance, fieldnames):
    """Deletes files from filesystem when object is deleted."""
    for fieldname in fieldnames:
        filefield = getattr(instance, fieldname, None)
        if filefield:
            if os.path.isfile(filefield.path):
                os.remove(filefield.path)


def auto_delete_files_on_instance_change(instance, fieldnames, model):
    """Deletes files from filesystem when object is changed."""
    if not instance.pk:
        return  # instance not yet saved in database
    try:
        old_instance = model.objects.get(pk=instance.pk)
    except model.DoesNotExist:
        return  # old version gone from database entirely
    for fieldname in fieldnames:
        old_filefield = getattr(old_instance, fieldname, None)
        if not old_filefield:
            continue
        new_filefield = getattr(instance, fieldname, None)
        if old_filefield != new_filefield:
            if os.path.isfile(old_filefield.path):
                os.remove(old_filefield.path)


# =============================================================================
# Action-restricted ModelAdmin classes
# =============================================================================

class ReadOnlyChangeList(ChangeList):
    # See ChangeList in django.contrib.admin.views.main
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_popup:
            title = ugettext('Select %s')
        else:
            title = ugettext('Select %s to view')
        self.title = title % force_text(self.opts.verbose_name)


class ReadOnlyModelAdmin(admin.ModelAdmin):
    """
    Allows view ("change"), but not add/edit/delete.

    You also need to do this:
        my_admin_site.index_template = 'admin/viewchange_admin_index.html'
    ... to give a modified admin/index.html that says "View/change" not
    "Change".

    """
    # http://stackoverflow.com/questions/3068843/permission-to-view-but-not-to-change-django  # noqa
    # See also http://stackoverflow.com/questions/6680631/django-admin-separate-read-only-view-and-change-view  # noqa

    # Remove the tickbox for deletion, and the top/bottom action bars:
    actions = None

    # When you drill down into a single object, use a custom template
    # that removes the 'save' buttons:
    change_form_template = 'admin/readonly_view_form.html'

    def has_add_permission(self, request, obj=None):
        # Don't let the user add objects.
        return False

    def has_delete_permission(self, request, obj=None):
        # Don't let the user delete objects.
        return False

    # Don't remove has_change_permission, or you won't see anything.
    # def has_change_permission(self, request, obj=None):
    #     return False

    def save_model(self, request, obj, form, change):
        # Return nothing to make sure user can't update any data
        pass

    # Make list say "Select [model] to view" not "... change"
    def get_changelist(self, request, **kwargs):
        return ReadOnlyChangeList

    # Make single object view say "View [model]", not "Change [model]"
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context["title"] = "View %s" % force_text(
            self.model._meta.verbose_name)
        return super().change_view(request, object_id, form_url,
                                   extra_context=extra_context)


class AddOnlyModelAdmin(admin.ModelAdmin):
    """
    Allows add, but not edit or delete.
    Optional extra class attribute:
        fields_for_viewing
    """
    actions = None

    # When you drill down into a single object, use a custom template
    # that removes the 'save' buttons:
    change_form_template = 'admin/readonly_view_form.html'

    # But keep the default for adding:
    add_form_template = 'admin/change_form.html'

    def has_delete_permission(self, request, obj=None):
        return False

    def get_changelist(self, request, **kwargs):
        return ReadOnlyChangeList

    # This is an add-but-not-edit class.
    # http://stackoverflow.com/questions/7860612/django-admin-make-field-editable-in-add-but-not-edit  # noqa
    def get_readonly_fields(self, request, obj=None):
        if obj:  # obj is not None, so this is an edit
            # self.__class__ is the derived class
            if hasattr(self.__class__, 'fields_for_viewing'):
                return self.__class__.fields_for_viewing
            elif hasattr(self.__class__, 'readonly_fields'):
                return self.__class__.readonly_fields
            else:
                return self.__class__.fields
        else:  # This is an addition
            return []

    def get_fields(self, request, obj=None):
        if obj:  # edit (view)
            return self.__class__.fields_for_viewing
        else:
            return self.__class__.fields

    # Make single object view say "View [model]", not "Change [model]"
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context["title"] = "View %s" % force_text(
            self.model._meta.verbose_name)
        return super().change_view(request, object_id, form_url,
                                   extra_context=extra_context)


class EditOnlyModelAdmin(admin.ModelAdmin):
    """
    Allows editing, but not add or delete.
    Designed for e.g. when you have a fixed set of PKs.
    In that situation, ensure the PK field is in readonly_fields.
    """
    actions = None

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================================
# Disable boolean icons for a ModelAdmin field
# =============================================================================
# http://stackoverflow.com/questions/13990846/disable-on-off-icon-for-boolean-field-in-django  # noqa
# ... extended to use closures

def disable_bool_icon(fieldname, model):
    def func(self, obj):
        return getattr(obj, fieldname)
    func.boolean = False
    func.admin_order_field = fieldname
    func.short_description = \
        model._meta.get_field_by_name(fieldname)[0].verbose_name
    return func


# =============================================================================
# Multiple values from a text area
# =============================================================================

def clean_int(x):
    try:
        return int(x)
    except ValueError:
        raise forms.ValidationError(
            "Cannot convert to integer: {}".format(repr(x)))


def clean_nhs_number(x):
    try:
        x = int(x)
        if not is_valid_nhs_number(x):
            raise ValueError
        return x
    except ValueError:
        raise forms.ValidationError(
            "Not a valid NHS number: {}".format(repr(x)))


class MultipleIntAreaField(forms.Field):
    # See also http://stackoverflow.com/questions/29303902/django-form-with-list-of-integers  # noqa
    widget = forms.Textarea

    def clean(self, value):
        return [clean_int(x) for x in value.split()]


class MultipleNhsNumberAreaField(forms.Field):
    widget = forms.Textarea

    def clean(self, value):
        return [clean_nhs_number(x) for x in value.split()]


class MultipleWordAreaField(forms.Field):
    widget = forms.Textarea

    def clean(self, value):
        return value.split()


class SingleNhsNumberField(forms.IntegerField):
    def clean(self, value):
        return clean_nhs_number(value)
