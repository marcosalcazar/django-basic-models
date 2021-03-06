# Copyright 2011 Concentric Sky, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from django.contrib.admin import ModelAdmin
from django.utils.translation import ugettext_lazy, ugettext as _
from django.contrib.admin.util import model_ngettext
from django.db import transaction


__all__ = ['UserModelAdmin', 'DefaultModelAdmin', 'SlugModelAdmin', 'OneActiveAdmin']


class UserModelAdmin(ModelAdmin):
    """ModelAdmin subclass that will automatically update created_by and updated_by fields"""
    save_on_top = True
    readonly_fields = ('created_by', 'updated_by')

    def save_model(self, request, obj, form, change):
        instance = form.save(commit=False)
        self._update_instance(instance, request.user)
        instance.save()
        return instance

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        try:
            # For Django 1.7+
            for obj in formset.deleted_objects:
                obj.delete()
        except AssertionError:
            # Django 1.6 and earlier already deletes the objects, trying to
            # delete them a second time raises an AssertionError.
            pass

        for instance in instances:
            self._update_instance(instance, request.user)
            instance.save()
        formset.save_m2m()

    @staticmethod
    def _update_instance(instance, user):
        if not instance.pk:
            instance.created_by = user
        instance.updated_by = user


class ActiveModelAdmin(ModelAdmin):
    """ModelAdmin subclass that adds activate and delete actions and situationally removes the delete action"""
    actions = ['activate_objects', 'deactivate_objects']

    @transaction.atomic
    def _set_objects_active(self, request, queryset, active):
        """ Sets the 'is_active' property of each item in ``queryset`` to ``active`` and reports success to the user. """
        # We call save on each object instead of using queryset.update to allow for custom save methods and hooks.
        count = 0
        for obj in queryset.select_for_update():
            obj.is_active = active
            obj.save(update_fields=['is_active'])
            count += 1
        self.message_user(request, _("Successfully %(prefix)sactivated %(count)d %(items)s.") % {
            "prefix": "" if active else "de", "count": count, "items": model_ngettext(self.opts, count)
        })

    def activate_objects(self, request, queryset):
        """Admin action to set is_active=True on objects"""
        self._set_objects_active(request, queryset, True)
    activate_objects.short_description = "Activate selected %(verbose_name_plural)s"

    def deactivate_objects(self, request, queryset):
        """Admin action to set is_active=False on objects"""
        self._set_objects_active(request, queryset, False)
    deactivate_objects.short_description = "Deactivate selected %(verbose_name_plural)s"

    def get_actions(self, request):
        actions = super(ActiveModelAdmin, self).get_actions(request)
        if not self.has_delete_permission(request):
            if 'delete_selected' in actions:
                del actions['delete_selected']
        return actions


class TimestampedModelAdmin(ModelAdmin):
    """ModelAdmin subclass that will set created_at and updated_at fields to readonly"""
    readonly_fields = ('created_at', 'updated_at')


class DefaultModelAdmin(ActiveModelAdmin, UserModelAdmin, TimestampedModelAdmin):
    """ModelAdmin subclass that combines functionality of UserModel, ActiveModel, and TimestampedModel admins and defines a Meta fieldset"""
    readonly_fields = ('created_at', 'created_by', 'updated_at', 'updated_by')
    fieldsets = (
        ('Meta', {'fields': ('is_active', 'created_at', 'created_by', 'updated_at', 'updated_by'), 'classes': ('collapse',)}),
    )


class SlugModelAdmin(DefaultModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ('name', 'slug', 'is_active')
    fieldsets = (
        (None, {'fields': ('name', 'slug')}),
    ) + DefaultModelAdmin.fieldsets


class OneActiveAdmin(ModelAdmin):
    save_on_top = True
    list_display = ('__unicode__', 'is_active')
    change_form_template = "admin/preview_change_form.html"
    actions = ['duplicate']

    def duplicate(self, request, queryset):
        for object in queryset:
            object.clone()
    duplicate.short_description = ugettext_lazy("Duplicate selected %(verbose_name_plural)s")
