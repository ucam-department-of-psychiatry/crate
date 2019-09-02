## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/tree/panels/nlp.mako
<%inherit file="../base.mako"/>
<%!

STARTCOLS = [
    "_srcdatetimeval AS 'Source time'",
]
ENDCOLS = [
    "_when_fetched_utc AS 'NLP time'",
]
COMMON_END_COLUMNS = [
    "_content", "relation", "tense",
] + ENDCOLS
SIMPLE_NUMERIC_COLUMNS = [
    "value_text", "units",
] + COMMON_END_COLUMNS
NUMERATOR_DENOMINATOR_COLUMNS = [
    "numerator", "denominator",
] + COMMON_END_COLUMNS
NLP_DEFINITIONS = (
    # tablename, description, columns

    ("ace", "Addenbrooke’s Cognitive Examination",
     STARTCOLS + ["out_of_100"] + NUMERATOR_DENOMINATOR_COLUMNS),

    ("basophils", "Basophil count",
     STARTCOLS + ["value_billion_per_l"] + SIMPLE_NUMERIC_COLUMNS),

    ("crp", "C-reactive protein",
     STARTCOLS + ["value_mg_l"] + SIMPLE_NUMERIC_COLUMNS),

    ("drugs", "Drugs (via MedEx)",
     STARTCOLS + [
        "drug", "generic_name", "brand",
         "form", "strength", "dose_amount", "route",
        "frequency", "duration", "necessity",
        "sentence_text",
     ] + ENDCOLS),
)

%>

<div>

    <h1><a id="_top"></a>Natural Language Processing (NLP) results</h1>
    <p>“Source time” is when the record relates to.
        “NLP time” is when the NLP software processed this data.</p>

    <ul>
        %for tablename, description, columns in NLP_DEFINITIONS:
            <li><a href="#${tablename}">${description}</a></li>
        %endfor
    </ul>

    %for tablename, description, columns in NLP_DEFINITIONS:
        <%include file="../snippets/nlp_section.mako" args="tablename=tablename, description=description, columns=columns"/>
    %endfor

</div>
