# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.apps import apps
from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.core.management import call_command
from django.db import connection, models
from django.db.models.signals import pre_migrate
from django.db.utils import ProgrammingError
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from . import conf

if conf.AUTOCREATE_DB:
    @receiver(pre_migrate, sender=apps.get_app_config('anonymized_activity_log'))
    def createdb(sender, using, **kwargs):
        db = settings.DATABASES[conf.LOG_DB_KEY]['NAME']
        with connection.cursor() as cursor:
            try:
                cursor.execute("CREATE DATABASE {}".format(db))
            except ProgrammingError:
                pass

        if using == 'default':
            call_command('migrate', database=conf.LOG_DB_KEY)


class ActivityLog(models.Model):
    user = models.CharField(_('user'), max_length=256)
    request_url = models.CharField(_('url'), max_length=256)
    request_method = models.CharField(_('http method'), max_length=10)
    response_code = models.CharField(_('response code'), max_length=3)
    datetime = models.DateTimeField(_('datetime'), default=timezone.now)
    extra_data = JSONField(_('extra data'), blank=True, null=True)  # TODO find a way to remove dependency on psycopg2
    ip_address = models.GenericIPAddressField(
        _('user IP'), null=True, blank=True)

    session_id = models.CharField(max_length=256, null=True)
    request_path = models.TextField()
    request_query_string = models.TextField()
    request_vars = models.TextField()

    request_secure = models.BooleanField(default=False)
    request_ajax = models.BooleanField(default=False)
    request_meta = models.TextField(null=True, blank=True)

    view_function = models.CharField(max_length=256)
    view_doc_string = models.TextField(null=True, blank=True)
    view_args = models.TextField()

    class Meta:
        verbose_name = _('activity log')
