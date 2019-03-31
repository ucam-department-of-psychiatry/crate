#!/usr/bin/env python

"""
crate_anon/crateweb/research/forms.py

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

**Django forms for the research site.**

"""

import datetime
import logging
from typing import Any, Dict, List, Optional, Type

from cardinal_pythonlib.django.forms import (
    MultipleIntAreaField,
    MultipleWordAreaField,
)
from django import forms
from django.forms import (
    BooleanField,
    CharField,
    ChoiceField,
    DateField,
    FileField,
    FloatField,
    IntegerField,
    ModelForm,
)

from crate_anon.crateweb.research.models import Highlight, Query
from crate_anon.crateweb.research.research_db_info import SingleResearchDatabase  # noqa
from crate_anon.common.sql import (
    SQL_OPS_MULTIPLE_VALUES,
    SQL_OPS_VALUE_UNNECESSARY,
    QB_DATATYPE_DATE,
    QB_DATATYPE_FLOAT,
    QB_DATATYPE_INTEGER,
    QB_DATATYPE_UNKNOWN,
    QB_STRING_TYPES,
)

log = logging.getLogger(__name__)


class AddQueryForm(ModelForm):
    """
    Form to add or edit an SQL
    :class:`crate_anon.crateweb.research.models.Query`.
    """
    class Meta:
        model = Query
        fields = ['sql']
        widgets = {
            'sql': forms.Textarea(attrs={'rows': 20, 'cols': 80}),
        }


class BlankQueryForm(ModelForm):
    """
    Unused? For :class:`crate_anon.crateweb.research.models.Query`.
    """
    class Meta:
        model = Query
        fields = []


class AddHighlightForm(ModelForm):
    """
    Form to add/edit a :class:`crate_anon.crateweb.research.models.Highlight`.
    """
    class Meta:
        model = Highlight
        fields = ['colour', 'text']


class BlankHighlightForm(ModelForm):
    """
    Unused? For :class:`crate_anon.crateweb.research.models.Highlight`.
    """
    class Meta:
        model = Highlight
        fields = []


class DatabasePickerForm(forms.Form):
    """
    Form to choose a research database.
    """
    database = ChoiceField(label="Database", required=True)

    def __init__(self,
                 *args,
                 dbinfolist: List[SingleResearchDatabase],
                 **kwargs) -> None:
        """
        Args:
            dbinfolist:
                list of all
                :class:`crate_anon.crateweb.research.research_db_info.SingleResearchDatabase`.
        """  # noqa
        super().__init__(*args, **kwargs)
        f = self.fields['database']  # type: ChoiceField
        f.choices = [(d.name, d.description) for d in dbinfolist]


class PidLookupForm(forms.Form):
    """
    Form to look up patient IDs from RIDs, MRIDs, and/or TRIDs.

    For the RDBM.
    """
    rids = MultipleWordAreaField(required=False)
    mrids = MultipleWordAreaField(required=False)
    trids = MultipleIntAreaField(required=False)

    def __init__(self,
                 *args,
                 dbinfo: SingleResearchDatabase,
                 **kwargs) -> None:
        """
        Args:
            dbinfo:
                research database to look up descriptions from, as a
                :class:`crate_anon.crateweb.research.research_db_info.SingleResearchDatabase` 
        """  # noqa
        super().__init__(*args, **kwargs)
        rids = self.fields['rids']  # type: MultipleIntAreaField
        mrids = self.fields['mrids']  # type: MultipleIntAreaField
        trids = self.fields['trids']  # type: MultipleIntAreaField
        rids.label = f"{dbinfo.rid_field}: {dbinfo.rid_description} (RID)"
        mrids.label = f"{dbinfo.mrid_field}: {dbinfo.mrid_description} (MRID)"
        trids.label = f"{dbinfo.trid_field}: {dbinfo.trid_description} (TRID)"


class RidLookupForm(forms.Form):
    """
    Form to look up RIDs from PIDs/MPIDs.

    For clinicians: "get the RID for my patient".
    """
    pids = MultipleWordAreaField(required=False)
    mpids = MultipleWordAreaField(required=False)

    def __init__(self,
                 *args,
                 dbinfo: SingleResearchDatabase,
                 **kwargs) -> None:
        """
        Args:
            dbinfo:
                research database to look up descriptions from, as a
                :class:`crate_anon.crateweb.research.research_db_info.SingleResearchDatabase` 
        """  # noqa
        super().__init__(*args, **kwargs)
        pids = self.fields['pids']  # type: MultipleIntAreaField
        mpids = self.fields['mpids']  # type: MultipleIntAreaField
        pids.label = f"{dbinfo.pid_description} (PID)"
        mpids.label = f"{dbinfo.mpid_description} (MPID)"


DEFAULT_MIN_TEXT_FIELD_LENGTH = 100


class FieldPickerInfo(object):
    """
    Describes a database field for when the user is asked to choose one via a
    web form.
    """
    def __init__(self, value: str, description: str, type_: Type,
                 permits_empty_id: bool) -> None:
        self.value = value
        self.description = description
        self.type_ = type_
        self.permits_empty_id = permits_empty_id


class SQLHelperFindAnywhereForm(forms.Form):
    """
    Base class for finding something anywhere in a patient's record.

    The user gets to pick

    - a field name (consistent across tables) representing a patient research
      ID (see :class:`FieldPickerInfo`);
    - a RID value
    - options to restrict which text fields are searched
    - an option to use full-text indexing where available
    - display options

    The subclasses then choose what the user should search for.
    """
    fkname = ChoiceField(required=True)
    patient_id = CharField(label="ID value (to restrict to a single patient)",
                           required=False)
    use_fulltext_index = BooleanField(
        label="Use full-text indexing where available "
        "(faster, but requires whole words)",
        required=False)
    min_length = IntegerField(
        label=f"Minimum 'width' of textual field to include "
              f"(e.g. {DEFAULT_MIN_TEXT_FIELD_LENGTH})",
        min_value=1, required=True)
    include_content = BooleanField(
        label="Include content from fields where found (slower)",
        required=False)
    include_datetime = BooleanField(
        label="Include date/time where known",
        required=False)

    def __init__(
            self,
            *args,
            fk_options: List[FieldPickerInfo],
            fk_label: str = "Field name containing patient research ID",
            **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fk_options = fk_options
        # Set the choices available for fkname
        f = self.fields['fkname']  # type: ChoiceField
        f.choices = [(opt.value, opt.description) for opt in fk_options]
        f.label = fk_label

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()
        fieldname = cleaned_data.get("fkname")
        pidvalue = cleaned_data.get("patient_id")
        if fieldname:
            opt = next(o for o in self.fk_options if o.value == fieldname)
            if pidvalue:
                try:
                    _ = opt.type_(pidvalue)
                except (TypeError, ValueError):
                    raise forms.ValidationError(
                        f"For field {opt.description!r}, the ID value must be "
                        f"of type {opt.type_}")
            else:
                self._check_permits_empty_id_for_blank_id(opt)
        return cleaned_data

    def _check_permits_empty_id_for_blank_id(self,
                                             opt: FieldPickerInfo) -> None:
        # Exists as a function so ClinicianAllTextFromPidForm can override it.
        if not opt.permits_empty_id:
            raise forms.ValidationError(
                f"For this ID type ({opt.value}), "
                f"you must specify an ID value")


# class SQLHelperTextAnywhereForm(forms.Form):
#     """
#     Form for "find text anywhere in a patient's record".
#
#     The user gets to pick
#
#     - a field name (consistent across tables) representing a patient research
#       ID (see :class:`FieldPickerInfo`);
#     - a RID value
#     - details of the text to search for
#     - options to restrict which text fields are searched
#     - an option to use full-text indexing where available
#     - display options
#
#     This research-oriented form is then subclassed for clinicians; see
#     :class:`ClinicianAllTextFromPidForm`.
#     """
#     fkname = ChoiceField(required=True)
#     patient_id = CharField(label="ID value (to restrict to a single patient)",
#                            required=False)
#     fragment = CharField(label="String fragment to find", required=True)
#     use_fulltext_index = BooleanField(
#         label="Use full-text indexing where available "
#         "(faster, but requires whole words)",
#         required=False)
#     min_length = IntegerField(
#         label="Minimum 'width' of textual field to include (e.g. {})".format(
#             DEFAULT_MIN_TEXT_FIELD_LENGTH
#         ),
#         min_value=1, required=True)
#     include_content = BooleanField(
#         label="Include content from fields where found (slower)",
#         required=False)
#     include_datetime = BooleanField(
#         label="Include date/time from where known",
#         required=False)
#
#     def __init__(
#             self,
#             *args,
#             fk_options: List[FieldPickerInfo],
#             fk_label: str = "Field name containing patient research ID",
#             **kwargs) -> None:
#         super().__init__(*args, **kwargs)
#         self.fk_options = fk_options
#         # Set the choices available for fkname
#         f = self.fields['fkname']  # type: ChoiceField
#         f.choices = [(opt.value, opt.description) for opt in fk_options]
#         f.label = fk_label
#
#     def clean(self) -> Dict[str, Any]:
#         cleaned_data = super().clean()
#         fieldname = cleaned_data.get("fkname")
#         pidvalue = cleaned_data.get("patient_id")
#         if fieldname:
#             opt = next(o for o in self.fk_options if o.value == fieldname)
#             if pidvalue:
#                 try:
#                     _ = opt.type_(pidvalue)
#                 except (TypeError, ValueError):
#                     raise forms.ValidationError(
#                         "For field {!r}, the ID value must be of "
#                         "type {}".format(opt.description, opt.type_))
#             else:
#                 self._check_permits_empty_id_for_blank_id(opt)
#         return cleaned_data
#
#     def _check_permits_empty_id_for_blank_id(self,
#                                              opt: FieldPickerInfo) -> None:
#         # Exists as a function so ClinicianAllTextFromPidForm can override it.
#         if not opt.permits_empty_id:
#             raise forms.ValidationError(
#                 "For this ID type ({}), you must specify an ID "
#                 "value".format(opt.value))


class SQLHelperTextAnywhereForm(SQLHelperFindAnywhereForm):
    """
    Form for "find text anywhere in a patient's record".

    The user gets to pick

    - a field name (consistent across tables) representing a patient research
      ID (see :class:`FieldPickerInfo`);
    - a RID value
    - details of the text to search for
    - options to restrict which text fields are searched
    - an option to use full-text indexing where available
    - display options

    This research-oriented form is then subclassed for clinicians; see
    :class:`ClinicianAllTextFromPidForm`.
    """
    fragment = CharField(label="String fragment to find", required=True)

    def __init__(
            self,
            *args,
            **kwargs) -> None:
        super().__init__(*args, **kwargs)


class ClinicianAllTextFromPidForm(SQLHelperTextAnywhereForm):
    """
    A slightly restricted form of :class:`SQLHelperTextAnywhereForm` for
    clinicians.

    The clinician version always requires an ID (no "patient browsing"; that's
    in the domain of research as it might yield patients that aren't being
    cared for by this clinician).
    """
    patient_id = CharField(label="ID value", required=True)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args,
                         fk_label="Field name containing patient ID",
                         **kwargs)
        inccontent = self.fields['include_content']  # type: BooleanField
        incdate = self.fields['include_datetime']  # type: BooleanField

        # Hide include_content/include_datetime (always true here)
        # inccontent.widget = inccontent.hidden_widget  # ... nope!
        inccontent.widget = forms.HiddenInput()  # yes, this works
        incdate.widget = forms.HiddenInput()

    def _check_permits_empty_id_for_blank_id(self,
                                             opt: FieldPickerInfo) -> None:
        return


class SQLHelperDrugTypeForm(SQLHelperFindAnywhereForm):
    """
    Form for "find drug of a given type anywhere in a patient's record".

    Same as 'SQLHelperTextAnywhereForm' except the user picks a drug type to
    search for instead of a string fragment.
    """
    # Left these all in because I didn't know which ones would be useful
    DRUG_TYPES = (
        ('antidepressant', 'antidepressant'),
        ('conventional_antidepressant', 'conventional_antidepressant'),
        ('ssri', 'ssri'),
        ('non_ssri_modern_antidepressant', 'non_ssri_modern_antidepressant'),
        ('tricyclic_antidepressant', 'tricyclic_antidepressant'),
        ('tetracyclic_and_related_antidepressant',
         'tetracyclic_and_related_antidepressant'),
        ('monoamine_oxidase_inhibitor', 'monoamine_oxidase_inhibitor'),
        ('antipsychotic', 'antipsychotic'),
        ('first_generation_antipsychotic', 'first_generation_antipsychotic'),
        ('second_generation_antipsychotic', 'second_generation_antipsychotic'),
        ('stimulant', 'stimulant'),
        ('anticholinergic', 'anticholinergic'),
        ('benzodiazepine', 'benzodiazepine'),
        ('z_drug', 'z_drug'),
        ('non_benzodiazepine_anxiolytic', 'non_benzodiazepine_anxiolytic'),
        ('gaba_a_functional_agonist', 'gaba_a_functional_agonist'),
        ('gaba_b_functional_agonist', 'gaba_b_functional_agonist'),
        ('mood_stabilizer', 'mood_stabilizer'),
        # Endocrinology
        ('antidiabetic', 'antidiabetic'),
        ('sulfonylurea', 'sulfonylurea'),
        ('biguanide', 'biguanide'),
        ('glifozin', 'glifozin'),
        ('glp1_agonist', 'glp1_agonist'),
        ('dpp4_inhibitor', 'dpp4_inhibitor'),
        ('meglitinide', 'meglitinide'),
        ('thiazolidinedione', 'thiazolidinedione'),
        # Cardiovascular
        ('cardiovascular', 'cardiovascular'),
        ('beta_blocker', 'beta_blocker'),
        ('ace_inhibitor', 'ace_inhibitor'),
        ('statin', 'statin'),
        # Respiratory
        ('respiratory', 'respiratory'),
        ('beta_agonist', 'beta_agonist'),
        # Gastrointestinal
        ('gastrointestinal', 'gastrointestinal'),
        ('proton_pump_inhibitor', 'proton_pump_inhibitor'),
        ('nonsteroidal_anti_inflammatory', 'nonsteroidal_anti_inflammatory'),
        # Nutritional
        ('vitamin', 'vitamin')
    )
    drug_type = ChoiceField(label="Drug type to find", required=True)

    def __init__(
            self,
            *args,
            drug_options: List[str] = DRUG_TYPES,
            **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields['drug_type'].choices = drug_options


def html_form_date_to_python(text: str) -> datetime.datetime:
    """
    Converts a date from the textual form used in HTML forms to a Python
    ``datetime.datetime`` object.

    Args:
        text: text to convert

    Returns:
        a ``datetime.datetime``
    """
    return datetime.datetime.strptime(text, "%Y-%m-%d")


def int_validator(text: str) -> str:
    """
    Takes text and returns a string version of an integer version of it.

    Args:
        text:

    Returns:
        the same thing, usually (though any redundant ".0" will be removed)

    Raises:
        :exc:`TypeError` or :exc:`ValueError` if something is wrong

    """
    return str(int(text))  # may raise ValueError, TypeError


def float_validator(text: str) -> str:
    """
    Takes text and returns a string version of a float version of it.

    Args:
        text:

    Returns:
        the same thing, usually

    Raises:
        :exc:`TypeError` or :exc:`ValueError` if something is wrong

    """
    return str(float(text))  # may raise ValueError, TypeError


class QueryBuilderForm(forms.Form):
    """
    Form to build an SQL query using a web interface.

    Works hand in hand with ``querybuilder.js`` on the client side; q.v.
    """

    database = CharField(label="Schema", required=False)
    schema = CharField(label="Schema", required=True)
    table = CharField(label="Table", required=True)
    column = CharField(label="Column", required=True)
    datatype = CharField(label="Data type", required=True)
    offer_where = BooleanField(label="Offer WHERE?", required=False)
    # BooleanField generally needs "required=False", or you can't have False!
    where_op = CharField(label="WHERE comparison", required=False)

    date_value = DateField(label="Date value (e.g. 1900-01-31)",
                           required=False)
    int_value = IntegerField(label="Integer value", required=False)
    float_value = FloatField(label="Float value", required=False)
    string_value = CharField(label="String value", required=False)
    file = FileField(label="File (for IN)", required=False)

    def __init__(self, *args, **kwargs) -> None:
        self.file_values_list = []
        super().__init__(*args, **kwargs)

    def get_datatype(self) -> Optional[str]:
        return self.data.get('datatype', None)

    def is_datatype_unknown(self) -> bool:
        return self.get_datatype() == QB_DATATYPE_UNKNOWN

    def offering_where(self) -> bool:
        if self.is_datatype_unknown():
            return False
        return self.data.get('offer_where', False)

    def get_value_fieldname(self) -> str:
        datatype = self.get_datatype()
        if datatype == QB_DATATYPE_INTEGER:
            return "int_value"
        if datatype == QB_DATATYPE_FLOAT:
            return "float_value"
        if datatype == QB_DATATYPE_DATE:
            return "date_value"
        if datatype in QB_STRING_TYPES:
            return "string_value"
        if datatype == QB_DATATYPE_UNKNOWN:
            return ""
        raise ValueError("Invalid field type")

    def get_cleaned_where_value(self) -> Any:
        # Only call this if you've already cleaned/validated the form!
        return self.cleaned_data[self.get_value_fieldname()]

    def clean(self) -> None:
        # Check the WHERE information is sufficient.
        if 'submit_select' in self.data or 'submit_select_star' in self.data:
            # Form submitted via the "Add" method, so no checks required.
            # http://stackoverflow.com/questions/866272/how-can-i-build-multiple-submit-buttons-django-form  # noqa
            return
        if not self.offering_where():
            return
        cleaned_data = super().clean()
        if not cleaned_data['where_op']:
            self.add_error('where_op',
                           forms.ValidationError("Must specify comparison"))

        # No need for a value for NULL-related comparisons. But otherwise:
        where_op = cleaned_data['where_op']
        if where_op not in SQL_OPS_VALUE_UNNECESSARY + SQL_OPS_MULTIPLE_VALUES:
            # Can't take 0 or many parameters, so need the standard single
            # value:
            value_fieldname = self.get_value_fieldname()
            value = cleaned_data.get(value_fieldname)
            if not value:
                self.add_error(
                    value_fieldname,
                    forms.ValidationError("Must specify WHERE condition"))

        # ---------------------------------------------------------------------
        # Special processing for file upload operations
        # ---------------------------------------------------------------------
        if where_op not in SQL_OPS_MULTIPLE_VALUES:
            return
        fileobj = cleaned_data['file']
        # ... is an instance of InMemoryUploadedFile
        if not fileobj:
            self.add_error('file', forms.ValidationError("Must specify file"))
            return

        datatype = self.get_datatype()
        if datatype in QB_STRING_TYPES:
            form_to_python_fn = str
        elif datatype == QB_DATATYPE_DATE:
            form_to_python_fn = html_form_date_to_python
        elif datatype == QB_DATATYPE_INTEGER:
            form_to_python_fn = int_validator
        elif datatype == QB_DATATYPE_FLOAT:
            form_to_python_fn = float_validator
        else:
            # Safe defaults
            form_to_python_fn = str
        # Or: http://www.dabeaz.com/generators/Generators.pdf
        self.file_values_list = []
        for line in fileobj.read().decode("utf8").splitlines():
            raw_item = line.strip()
            if not raw_item or raw_item.startswith('#'):
                continue
            try:
                value = form_to_python_fn(raw_item)
            except (TypeError, ValueError):
                self.add_error('file', forms.ValidationError(
                    f"File contains bad value: {raw_item!r}"))
                return
            self.file_values_list.append(value)
        if not self.file_values_list:
            self.add_error('file', forms.ValidationError(
                "No values found in file"))


class ManualPeQueryForm(forms.Form):
    """
    Simple form for the "manual" section of the "Build Patient Explorer" page.

    Allows the user to enter raw SQL.
    """
    sql = CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 20, 'cols': 80})
    )
