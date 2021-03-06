# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import json

from django.conf import settings
from django.utils.module_loading import import_string as _load
from django.core.exceptions import DisallowedHost, ObjectDoesNotExist
from django.http import HttpResponseForbidden
from .models import ActivityLog
from . import conf

import hashlib


def get_ip_address(request):
    for header in conf.IP_ADDRESS_HEADERS:
        addr = request.META.get(header)
        if addr:
            return addr.split(',')[0].strip()


def get_extra_data(request, response, body):
    if not conf.GET_EXTRA_DATA:
        return
    if type(conf.GET_EXTRA_DATA) == str:
        return _load(conf.GET_EXTRA_DATA)(request, response, body)
    else:
        result = {}
        for f in conf.GET_EXTRA_DATA:
            data = _load(f)(request, response, body)
            result.update(data)


def get_encryption_function():
    return _load(conf.ENCRYPTION_FUNCTION)


def get_anonymization_function():
    return _load(conf.ANONYMIZATION_FUNCTION)


class ActivityLogMiddleware:
    def process_request(self, request):
        self._write_log(request)
        try:
            x = True
        except DisallowedHost:
            return HttpResponseForbidden()

    anonymization_function = get_anonymization_function()

    def process_response(self, request, response):
        the_record = self._get_log(request)
        miss_log = []
        if conf.STATUSES:
            miss_log.append(response.status_code not in conf.STATUSES)

        if conf.EXCLUDE_STATUSES:
            miss_log.append(response.status_code in conf.EXCLUDE_STATUSES)

        if any(miss_log):
            the_record.delete()
            return response

        the_record.response_code = response.status_code
        the_record.extra_data = get_extra_data(request, response, getattr(request, 'saved_body', ''))
        the_record.save()

        return response

    def _write_log(self, request):
        miss_log = [
            not (conf.ANONYMOUS or request.user.is_authenticated()),
            request.method not in conf.METHODS,
            any(url in request.path for url in conf.EXCLUDE_URLS)
        ]

        if any(miss_log):
            return

        user = self.anonymization_function(request)

        if request.method in ('GET', 'POST'):
            request_vars = json.dumps(getattr(request, request.method).__dict__)
        else:
            request_vars = None

        activity_log = ActivityLog(
            user=user,
            request_url=request.build_absolute_uri()[:255],
            request_method=request.method,
            ip_address=get_ip_address(request),
            request_path=request.path,
            request_query_string=request.META["QUERY_STRING"],
            request_vars=request_vars,
            request_secure=request.is_secure(),
            request_ajax=request.is_ajax(),
            request_meta=request.META.__str__(),
        )
        if hasattr(request, "session"):
            activity_log.session_id = request.session.session_key
        if hasattr(request, "user"):
            if request.user.is_authenticated():
                activity_log.requestUser = request.user

        activity_log.save()
        request.META['activity_log_id'] = activity_log.pk

    def _get_log(self, request):
        try:
            return ActivityLog.objects.get(pk=request.META['activity_log_id'])
        except ObjectDoesNotExist:
            return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        the_record = self._get_log(request)
        args = {"args": view_args, "kwargs": view_kwargs}
        if the_record:
            the_record.view_function = view_func.__name__
            the_record.view_doc_string = view_func.__doc__
            the_record.view_args = json.dumps(args)

            the_record.save()
