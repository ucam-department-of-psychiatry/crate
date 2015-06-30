#!/usr/bin/python2.7
# -*- encoding: utf8 -*-

"""
Test the anonymisation for specific databases.
"""

# =============================================================================
# Imports
# =============================================================================

import argparse
import collections
import csv
import logging
logger = logging.getLogger("test_anonymisation")
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.DEBUG)
import os

from anonymise import (
    config,
    extract_text,
    SRCFLAG,
)
from pythonlib.rnc_lang import AttrDict
from pythonlib.rnc_ui import mkdir_p


# =============================================================================
# Specific tests
# =============================================================================

def get_fieldinfo(args):
    """
    Fetches useful subsets from the data dictionary.
    """
    ddrows = config.dd.get_rows_for_dest_table(args.dsttable)
    textrow = next(x for x in ddrows
                   if x.dest_table == args.dsttable
                   and x.dest_field == args.dstfield)
    pkrow = next(x for x in ddrows
                 if SRCFLAG.PK in x.src_flags)
    pidrow = next(x for x in ddrows
                  if SRCFLAG.PRIMARYPID in x.src_flags)
    info = AttrDict({
        "pk_ddrow": pkrow,
        "pid_ddrow": pidrow,
        "text_ddrow": textrow,
    })
    logger.info("Using fields: {}".format(info))
    return info


def get_patientnum_rawtext(docid, fieldinfo):
    """
    Fetches the original text for a given document PK, plus the associated
    patient ID.
    """
    # *** ddrows = config.dd.get_rows_for_src_table(sourcedbname, sourcetable)
    db = config.sources[fieldinfo.text_ddrow.src_db]
    table = fieldinfo.text_ddrow.src_table
    textfield = fieldinfo.text_ddrow.src_field
    sourcedbname = fieldinfo.text_ddrow.src_db
    pidfield = fieldinfo.pid_ddrow.src_field
    pkfield = fieldinfo.pk_ddrow.src_field
    src_ddrows = config.dd.get_rows_for_src_table(sourcedbname, table)
    sourcefields = []
    idx_pidfield = None
    idx_textfield = None
    for i, ddr in enumerate(src_ddrows):
        sourcefields.append(ddr.src_field)
        if ddr.src_field == pidfield:
            idx_pidfield = i
        if ddr.src_field == textfield:
            idx_textfield = i
    if idx_pidfield is None:
        raise ValueError("Unknown idx_pidfield")
    if idx_textfield is None:
        raise ValueError("Unknown idx_textfield")
    query = """
        SELECT {fields}
        FROM {table}
        WHERE {pkfield} = ?
    """.format(
        fields=",".join(sourcefields),
        textfield=textfield,
        table=table,
        pkfield=pkfield,
    )
    # logger.debug("RAW: {}, {}".format(query, docid))
    row = db.fetchone(query, docid)
    if not row:
        return None, None
    pid = row[idx_pidfield]
    text = row[idx_textfield]
    if fieldinfo.text_ddrow._extract_text:
        text = extract_text(text, row, fieldinfo.text_ddrow, src_ddrows)
    return pid, text


def get_patientnum_anontext(docid, fieldinfo):
    """
    Fetches the anonymised text for a given document PK, plus the associated
    patient ID.
    """
    db = config.destdb
    table = fieldinfo.text_ddrow.dest_table
    textfield = fieldinfo.text_ddrow.dest_field
    pidfield = fieldinfo.pid_ddrow.dest_field
    pkfield = fieldinfo.pk_ddrow.dest_field
    query = """
        SELECT {pidfield}, {textfield}
        FROM {table}
        WHERE {pkfield} = ?
    """.format(
        pidfield=pidfield,
        textfield=textfield,
        table=table,
        pkfield=pkfield,
    )
    # logger.debug("ANON: {}, {}".format(query, docid))
    result = db.fetchone(query, docid)
    if not result:
        return None, None
    pid, text = result
    return pid, text


def process_doc(docid, args, fieldinfo, csvwriter, first):
    """
    Write the original and anonymised documents to disk, plus some
    counts to a CSV file.
    """
    # Get stuff
    patientnum, rawtext = get_patientnum_rawtext(docid, fieldinfo)
    patientnum2, anontext = get_patientnum_anontext(docid, fieldinfo)
    # patientnum is raw; patientnum2 is hashed
    # Write text
    rawfilename = os.path.join(args.rawdir,
                               "{}_{}.txt".format(patientnum, docid))
    anonfilename = os.path.join(args.anondir,
                                "{}_{}.txt".format(patientnum, docid))
    with open(rawfilename, 'w') as f:
        f.write(rawtext)
    with open(anonfilename, 'w') as f:
        f.write(anontext)

    n_patient = anontext.count(config.replace_patient_info_with)
    n_thirdparty = anontext.count(config.replace_third_party_info_with)
    n_nonspecific = anontext.count(config.replace_nonspecific_info_with)
    n_replacements = n_patient + n_thirdparty + n_nonspecific

    summary = collections.OrderedDict()
    summary["src_db"] = fieldinfo.text_ddrow.src_db
    summary["src_table"] = fieldinfo.text_ddrow.src_table
    summary["src_field_pid"] = fieldinfo.pid_ddrow.src_field
    summary["pid"] = patientnum
    summary["src_field_pk"] = fieldinfo.pk_ddrow.src_field
    summary["docid"] = docid
    summary["src_field_text"] = fieldinfo.text_ddrow.src_field
    summary["dest_table"] = fieldinfo.text_ddrow.dest_table
    summary["dest_field"] = fieldinfo.text_ddrow.dest_field
    summary["n_replacements"] = n_replacements
    # summary["n_patient"] = n_patient
    # summary["n_thirdparty"] = n_thirdparty
    # summary["n_nonspecific"] = n_nonspecific
    summary["word_count"] = len(rawtext.split())
    # ... use this to calculate true negatives (banal, visible) as:
    # true_negative = word_count - (true_pos + false_pos + false_neg)
    summary["true_positive_confidential_masked"] = "?"
    summary["false_negative_confidential_visible"] = "?"
    summary["false_positive_banal_masked"] = "?"
    summary["comments"] = ""

    if first:
        csvwriter.writerow(summary.keys())
    csvwriter.writerow(summary.values())


def get_docids(args, fieldinfo, from_src=True):
    """
    Generate a limited set of PKs for the documents.
    """
    if from_src:
        db = config.sources[fieldinfo.text_ddrow.src_db]
        table = fieldinfo.pk_ddrow.src_table
        pkfield = fieldinfo.pk_ddrow.src_field
    else:
        db = config.destdb
        table = fieldinfo.pk_ddrow.dest_table
        pkfield = fieldinfo.pk_ddrow.dest_field
    query = """
        SELECT {pkfield}
        FROM {table}
        ORDER BY {pkfield}
        LIMIT {limit}
    """.format(
        pkfield=pkfield,
        table=table,
        limit=args.limit,
    )
    return db.fetchallfirstvalues(query)


def test_anon(args):
    fieldinfo = get_fieldinfo(args)
    docids = get_docids(args, fieldinfo, args.from_src)
    mkdir_p(args.rawdir)
    mkdir_p(args.anondir)
    with open(args.resultsfile, 'wb') as csvfile:
        csvwriter = csv.writer(csvfile, delimiter='\t')
        first = True
        for docid in docids:
            process_doc(docid, args, fieldinfo, csvwriter, first)
            first = False
    logger.info("Finished. See {} for a summary.".format(args.resultsfile))
    logger.info(
        "Use meld to compare directories {} and {}".format(
            args.rawdir,
            args.anondir,
        )
    )
    logger.info("To install meld on Debian/Ubuntu: sudo apt-get install meld")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Test anonymisation')
    parser.add_argument('--config', required=True,
                        help='Configuration file name (input)')
    parser.add_argument('--dsttable', required=True,
                        help='Destination table')
    parser.add_argument('--dstfield', required=True,
                        help='Destination column')
    parser.add_argument('--limit', type=int, default=100,
                        help='Limit on number of documents')
    parser.add_argument('--rawdir', default='raw',
                        help='Directory for raw output text files')
    parser.add_argument('--anondir', default='anon',
                        help='Directory for anonymised output text files')
    parser.add_argument('--resultsfile', default='testanon_results.csv',
                        help='Results output CSV file name')
    parser.add_argument('--pkfromsrc', dest='from_src', action='store_true',
                        help='Fetch PKs (document IDs) from source (default)')
    parser.add_argument('--pkfromdest', dest='from_src', action='store_false',
                        help='Fetch PKs (document IDs) from destination')
    parser.set_defaults(from_src=True)
    args = parser.parse_args()

    # Load/validate config
    logger.info("Loading config...")
    config.set(filename=args.config)
    logger.info("... config loaded")

    # Do it
    test_anon(args)


if __name__ == '__main__':
    main()
