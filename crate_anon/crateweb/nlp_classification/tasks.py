"""
crate_anon/crateweb/nlp_classification/tasks.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

CRATE NLP classification Celery tasks.

"""

# Based on https://eeinte.ch/stream/progress-bar-django-using-celery/

from itertools import islice
import random

from celery import shared_task
from celery_progress.backend import ProgressRecorder

from django.conf import settings

from crate_anon.crateweb.nlp_classification.models import Sample, SourceRecord
from crate_anon.nlp_manager.constants import (
    FN_SRCPKVAL,
)


@shared_task(bind=True)
def create_source_records_from_sample(self, sample_pk: int) -> str:
    sample = Sample.objects.get(pk=sample_pk)

    batch_size = settings.CRATE_NLP_BATCH_SIZE
    source_column = sample.source_column

    source_connection = sample.get_source_database_connection()
    source_table_definition = source_column.table_definition
    source_table_name = source_table_definition.table_name
    source_pk_column_name = source_table_definition.pk_column_name
    source_column_name = source_column.name

    nlp_pk_column_name = sample.nlp_table_definition.pk_column_name
    nlp_table_name = sample.nlp_table_definition.table_name
    nlp_connection = sample.get_nlp_database_connection()

    where = f"{source_column_name} LIKE %s"
    params = [f"%{sample.search_term}%"]

    source_rows = source_connection.fetchall(
        [source_pk_column_name], source_table_name, where, params
    )
    total_rows = source_connection.count(source_table_name, where, params)

    rng = random.Random(sample.seed)
    # Lowest common denominator:
    # SQLite doesn't have big integer so the maximum bits is 32.
    # SQL Server does not have unsigned int types so we can't have 64 bits
    # and if we use a regular Integer, we can only store 31 bits
    max_rand_bits = 32

    progress_recorder = ProgressRecorder(self)

    start = 0

    while True:
        print(f"{start}/{total_rows}")
        progress_recorder.set_progress(
            start, total_rows, description="Creating source rows"
        )
        stop = start + batch_size

        source_pks = []

        for source_row in islice(source_rows, start, stop):
            print(source_row)
            source_pks.append(source_row[0])

        if not source_pks:
            break

        source_pk_format = ", ".join(["%s"] * len(source_pks))

        nlp_rows = nlp_connection.fetchall(
            [FN_SRCPKVAL, nlp_pk_column_name],
            nlp_table_name,
            where=f"{FN_SRCPKVAL} IN ({source_pk_format})",
            params=source_pks,
        )

        nlp_dict = {src_pk: nlp_pk for (src_pk, nlp_pk) in nlp_rows}

        for source_pk in source_pks:
            random_order = rng.getrandbits(max_rand_bits)
            source_record, created = SourceRecord.objects.get_or_create(
                random_order=random_order,
                source_column=sample.source_column,
                nlp_table_definition=sample.nlp_table_definition,
                source_pk_value=source_pk,
                nlp_pk_value=nlp_dict.get(source_pk, ""),
            )

            sample.source_records.add(source_record)

        start += len(source_pks)
