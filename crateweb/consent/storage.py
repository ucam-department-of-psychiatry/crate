#!/usr/bin/env python3
# consent/storage.py

from django.core.files.storage import FileSystemStorage
from django.conf import settings


privatestorage = FileSystemStorage(
    location=settings.PRIVATE_FILE_STORAGE_ROOT,
    base_url="/privatestorage")
