.. crate_anon/docs/source/nlp/nlprp.rst

..  Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).
    .
    This file is part of CRATE.
    .
    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

.. _ANSI SQL: http://www.contrib.andrew.cmu.edu/~shadow/sql/sql1992.txt
.. _authentication: https://en.wikipedia.org/wiki/Authentication
.. _authorization: https://en.wikipedia.org/wiki/Authorization
.. _GATE: https://gate.ac.uk/
.. _Grails: https://grails.org/
.. _HTTP: https://tools.ietf.org/html/rfc2616.html
.. _HTTP Accept-Encoding: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Encoding
.. _HTTP basic access authentication: https://en.wikipedia.org/wiki/Basic_access_authentication
.. _HTTP Content-Encoding: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Encoding
.. _HTTP digest access authentication: https://en.wikipedia.org/wiki/Digest_access_authentication
.. _ISO-8601: https://en.wikipedia.org/wiki/ISO_8601
.. _INFORMATION_SCHEMA: https://en.wikipedia.org/wiki/Information_schema
.. _JSON: https://www.json.org/
.. _Microsoft SQL Server: https://en.wikipedia.org/wiki/Microsoft_SQL_Server
.. _MySQL: https://www.mysql.com/
.. _OAuth: https://en.wikipedia.org/wiki/OAuth
.. _Oracle: https://en.wikipedia.org/wiki/Oracle_Database
.. _PostgreSQL: https://www.postgresql.org/
.. _RESTful: https://en.wikipedia.org/wiki/Representational_state_transfer
.. _Semantic Versioning: http://www.semver.org/
.. _SQLAlchemy: https://www.sqlalchemy.org/
.. _SQLite: https://www.sqlite.org/
.. _URL query string: https://en.wikipedia.org/wiki/Query_string
.. _UTC: https://en.wikipedia.org/wiki/Coordinated_Universal_Time


.. _nlprp:

Natural Language Processing Request Protocol (NLPRP)
----------------------------------------------------

**Version 0.2.0**

.. contents::
   :local:


Authors
~~~~~~~

In alphabetical order:

- Rudolf N. Cardinal (RNC), University of Cambridge, 2017-.
- Joe Kearney (JK), University of Cambridge, 2018.
- Angus Roberts (AR), King's College London, 2018-.
- Ian Roberts (IR), University of Sheffield, 2018-.
- Francesca Spivack (FS), University of Cambridge, 2018-.


Rationale
~~~~~~~~~

In the context of research using electronic medical records (EMR) systems, a
consideration is the need to derive structured data from free text, using
natural language processing (NLP) software.

However, not all individuals and/or institutions may have the necessary
resources to perform bulk NLP as they wish. In particular, there are two common
constraints. Firstly, the computing power necessary for NLP can be
considerable. Secondly, some NLP programs may be sensitive (for example, by
virtue of containing fragments of clinical free text from another institution,
used as an exemplar for an algorithm) and thus not widely distributable.
Accordingly, there is a need for a client–server NLP framework, and thus for a
defined request protocol.

The protocol is not RESTful_. In particular, it is not stateless.
State can be maintained on the server in between requests, if desired, through
the notion of queued requests.


Communications stack
~~~~~~~~~~~~~~~~~~~~

The underlying application layer is HTTP_ (and HTTPS, encrypted HTTP, is
strongly encouraged), over TCP/IP.


Request
~~~~~~~

Request format
^^^^^^^^^^^^^^

**Requests via HTTP POST**

Requests are always transmitted using the HTTP ``POST`` method.

- Rationale:

  (1) Some calls modify state on the server, making ``GET`` inappropriate.
  (2) Some requests will be large, making ``GET`` URL encoding inappropriate.
  (3) Many requests involve sensitive data, which should not be encoded into
      URLs via ``GET``.
  (4) Therefore, all requests are via ``POST`` [#getvspost]_.

- The POST method itself is broad [#rfc7231]_.

**Requests in JSON**

The request content is in JSON_, with media type ``application/json``. The
encoding can be specified, and will be assumed to be UTF-8 if not specified.

- Rationale: we need a structured notation supporting list types, key–value
  pair (KVP) types, a null notation, and arbitrary nesting. JSON fulfils this,
  is simple (and thus fast), is legible to humans, and is widely supported
  under many programming languages. Other formats such as XML require
  considerably more complex parsing and are slower [#soap]_.

- Consideration: denial-of-service attacks in which large quantities of
  nonsense are sent. We considered using XML instead of JSON as XML is
  intrinsically ordered; we could enforce a constraint of having call arguments
  such as parameter lists preceding textual content, and abandoning processing
  if the request is malformed. Instead, we elected to keep JSON but move
  authentication to the HTTP level (so non-authenticated requests can be thrown
  away earlier) and allow the server to impose its own choice of maximum
  request size. With that done, all requests coming through will be from
  authenticated users and of a reasonable request size. At that point, JSON
  continues to look simpler.

Note the JSON terminology:

- *Value:* one of:

  - *String:* zero or more Unicode characters, wrapped in double quotes, using
    backslash escapes.
  - *Number:* a raw number.
  - The literals ``true``, ``false``, or ``null``.
  - An *object* or *array*, as below.

- *Object:* an unordered collection of comma-separated KVPs bounded by braces,
  such as ``{key1: value1, key2: value2}``, where the keys are strings. Roughly
  equivalent to a Python dictionary.

- *Array:* an ordered collection of comma-separated values bounded by square
  brackets, such as ``[value1, value2]``. Equivalent to a Python list.

- JSON does *not* in general permit trailing commas in objects and arrays.

- Comments are not supported in JSON (but we may illustrate some JSON examples
  here using ``#`` to indicate comments).

Where versions are passed, they are in `Semantic Versioning`_ 2.0.0
format. Semantic versions are strings using a particular format
(e.g. ``"1.2.0"``), referred to as a Version henceforth.

Where date/time values are passed, they are in `ISO-8601`_ format
and must include all three of: date, time, timezone. (The choice of timezone is
immaterial; servers may choose to use UTC_ throughout.)


Authentication at HTTP/HTTPS level
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Servers are free to require an authentication_ method using a standard HTTP
  mechanism, such as `HTTP basic access authentication`_, `HTTP digest access
  authentication`_, a `URL query string`_, or `OAuth`_. The mechanism for
  doing so is not part of the API.

- It is expected that the HTTP front end would make the identity of an
  authenticated user available to the NLPRP server, e.g. so the server can
  check that a user is `authorized <authorization>`_ for a specific NLP
  processor or to impose volume/rate limits, but the mechanism for doing so is
  not part of the API specification.


Compression at HTTP/HTTPS level
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Clients may compress requests by setting the HTTP header ``Content-Encoding:
  gzip`` (see `HTTP Content-Encoding`_) and compressing the POST body
  accordingly. Servers should accept requests compressed with ``gzip``.

- If the client sets the ``Accept-Encoding`` header (see `HTTP
  Accept-Encoding`_), the server may return a suitably compressed response
  (indicated via the ``Content-Encoding`` header in its reply).


Rejection of unauthorized or malformed responses
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Servers may reject invalid responses with an HTTP error. Typical reasons
  might include failed authentication_ or authorization_; overly large
  requests; requests that exceed a user's quota; syntactically invalid NLPRP
  requests; syntactically valid requests that are invalid for this server (such
  as requests that include invalid processors).

- Clients must accept HTTP errors either with a NLPRP response or without.

  - If the body of the server's reply includes valid JSON where
    ``json_object["protocol"]["name"] == "nlprp"``, it is an NLPRP reply.

- If an error is returned via the NLP protocol, the ``status`` field in the
  response_ must match the HTTP status code.

- The rationale for this is to reduce the effect of denial-of-service attacks
  by preprocessing HTTP requests without the need to parse the NLPRP request
  content, and to allow NLPRP server software to operate within a broader
  institutional authentication, authorization, and/or accounting framework.


Request JSON structure
^^^^^^^^^^^^^^^^^^^^^^

The top-level structure of a request is a JSON object with the following keys.

.. rst-class:: nlprprequest

  .. list-table::
    :widths: 15 15 15 55
    :header-rows: 1

    * - Key
      - JSON type
      - Required?
      - Description

    * - ``protocol``
      - Object
      - Mandatory
      - Details of the NLPRP protocol that the client is using, with keys:

        - ``name`` (string): Must be ``"nlprp"``. Case insensitive.
        - ``version`` (string): The Version of the NLPRP protocol that the
          client is using.

    * - ``command``
      - String
      - Mandatory
      - NLPRP command, as below.

    * - ``args``
      - Value
      - Optional
      - Arguments to the command.

JSON does not care about whitespace in formatting, and neither the client nor
the server are under any obligation as to how they format their JSON.


.. _response:

Response
~~~~~~~~

Response format
^^^^^^^^^^^^^^^

The request is returned over HTTP as media type ``application/json``. The
encoding *should* be specified (e.g. ``application/json; charset=utf-8``, and
will be assumed to be UTF-8 if not specified.


Response JSON structure
^^^^^^^^^^^^^^^^^^^^^^^

The top-level structure of a response is a JSON object with the following keys.

.. rst-class:: nlprpresponse

  .. list-table::
    :widths: 15 15 15 55
    :header-rows: 1

    * - Key
      - JSON type
      - Required?
      - Description

    * - ``status``
      - Value
      - Mandatory
      - An integer matching the HTTP status code. Will be in the range [200,
        299] for success.

    * - ``errors``
      - Array
      - Optional
      - If the status is not in the range [200, 299], one or more errors will
        be given. Each error is an object with at least the following keys:

        - ``code`` (integer or null): error code
        - ``message`` (string): brief textual description of the error
        - ``description`` (string): more detail

    * - ``protocol``
      - Object
      - Mandatory
      - Details of the NLPRP protocol that the server is using. Keys:

        - ``name`` (string): Must be ``"nlprp"``. Case insensitive.
        - ``version`` (string): The Version of the NLPRP protocol that the
          client is using.

    * - ``server_info``
      - Object
      - Mandatory
      - Details of the NLPRP server. Keys:

        - ``name`` (string): Name of the NLPRP server software in use.
        - ``version`` (string): The Version of the NLPRP server software.


NLPRP commands
~~~~~~~~~~~~~~

.. _list_processors:

list_processors
^^^^^^^^^^^^^^^

No additional parameters are required, but there is an optional parameter.

.. rst-class:: nlprprequest

  .. list-table::
    :widths: 15 15 15 55
    :header-rows: 1

    * - Key
      - JSON type
      - Required?
      - Description

    * - ``sql_dialect``
      - String
      - Optional
      - The SQL dialect that the client would prefer to receive its column
        information in. (The server does not have to honour this.) See
        :ref:`SQL dialects <nlprp_sql_dialect>` below.
        *[Version 0.2.0 and higher.]*


This command lists the NLP processors available to the requestor. (This might
be a subset of all NLP processors on the server, depending on the
authentication and the permissions granted by the server.)

The relevant part of the response is:

.. rst-class:: nlprpresponse

  .. list-table::
    :widths: 15 15 15 55
    :header-rows: 1

    * - Key
      - JSON type
      - Required?
      - Description

    * - ``processors``
      - Array
      - Mandatory
      - An array of objects. Each object has the following keys:

        - ``name`` (string): the server’s name for the processor.
        - ``title`` (string): generally, the processor’s name for itself.
        - ``version`` (string): the Version of the processor.
        - ``is_default_version`` (Boolean): indicates that this processor is
          the default version for the given name. May be ``true`` for zero or
          one versions for a given processor name.
        - ``description`` (string): a description of the processor.
        - ``schema_type`` (string): optional; must be one of ``unknown``,
          ``tabular``; default is ``unknown``. (Future versions may add more
          schema types.)
          *[Version 0.2.0 and higher.]*
        - ``sql_dialect`` (string): the SQL dialect (see below) used within the
          ``tabular_schema`` object (see below). Must be present if
          ``tabular_schema`` is given.
          *[Version 0.2.0 and higher.]*
        - ``tabular_schema`` (object): an object that is present if and only if
          ``schema_type`` is ``tabular``. Represents a tabular schema and
          describing the tables/columns provided by this processor. The format
          of ``tabular_schema`` is described below.
          *[Version 0.2.0 and higher.]*

.. _nlprp_schema_definition:

**Schema definition**

The NLP server may not know the output format of its NLP processors, in which
case ``schema_type`` may be set to ``unknown``. However, this is undesirable.
Processors *should* describe their schema by enumerating their output
tables/columns if they provide output compatible with storage in database
tables. To do so, the server sets ``schema_type`` to ``tabular`` and provides
the ``tabular_schema`` object.

The ``tabular_schema`` object defines a tabular schema. It maps *table names*
to *arrays of column definition objects*. Thus, in pseudocode:

.. rst-class:: nlprpresponse

  .. code-block:: none

    "tabular_schema": {
        "table_name_1" : [
            <column_definition_1>,
            <column_definition_2>,
            ...
        ],
        "table_name_2" : [
            <column_definition_1>,
            <column_definition_2>,
            ...
        ],
        ...
    }

Most NLP processors produce output for a single database table. The table name
may be an empty string, ``""``, and that is fine (it is, after all, up to the
client to decide how it names its tables). Such a schema would look like this:

.. rst-class:: nlprpresponse

  .. code-block:: none

    "tabular_schema": {
        "" : [
            <column_definition_1>,
            <column_definition_2>,
            ...
        ]
    }

A few (e.g. GATE) processors may give output that requires more than one
database table to store. For example, a "people and places" processor may
return one kind of result when it finds a person, and another kind when it
finds a place; it would therefore need to define two tables.

Each column definition object describes a column in the database being used to
store results, and has the following keys.

.. rst-class:: nlprpresponse

  .. list-table::
    :header-rows: 1

    * - Key
      - JSON type
      - Required?
      - Description

    * - ``column_name``
      - String
      - Mandatory
      - Name of the column.

    * - ``column_type``
      - String
      - Mandatory
      - Full column data type, e.g. ``VARCHAR(64)``. (*)

    * - ``data_type``
      - String
      - Mandatory
      - Type name only, e.g. ``VARCHAR``

    * - ``is_nullable``
      - Boolean
      - Mandatory
      - Whether this column can contain ``null`` values.

    * - ``column_comment``
      - String or ``null``
      - Optional
      - Comment describing this column. (*)

    * - ``data_type``
      - String
      - Mandatory
      - Type name only, e.g. ``VARCHAR``

(The system follows the `ANSI SQL`_ INFORMATION_SCHEMA_ standard loosely;
specifically, using some of the columns found in
``INFORMATION_SCHEMA.COLUMNS``.)

  For examples of ``INFORMATION_SCHEMA.COLUMNS``, see e.g.

  - https://docs.microsoft.com/en-us/sql/relational-databases/system-information-schema-views/columns-transact-sql?view=sql-server-2017
  - https://www.postgresql.org/docs/current/infoschema-columns.html
  - https://dev.mysql.com/doc/refman/5.7/en/columns-table.html

(*) Not part of the ANSI standard; a MySQL extension to
``INFORMATION_SCHEMA.COLUMNS``.

.. _nlprp_sql_dialect:

**SQL dialects**

The ``sql_dialect`` parameter, detailed above, names the SQL dialect in which
``column_type`` and ``data_type`` are expressed. For example, "unlimited-length
text" might be ``VARCHAR(MAX)`` in the ``mssql`` dialect but ``LONGTEXT`` in
the ``mysql`` dialect.

SQL dialect values are strings representing those major dialects used by
SQLAlchemy_ (see https://docs.sqlalchemy.org/en/13/dialects/), i.e.

=============== ===============================================================
Dialect name    Dialect
=============== ===============================================================
``mysql``       MySQL_
``mssql``       `Microsoft SQL Server`_
``oracle``      Oracle_
``postgresql``  PostgreSQL_
``sqlite``      SQLite_
=============== ===============================================================


*Request example*

A full request as sent over TCP/IP might be as follows, being sent to
``https://myserver.mydomain/nlp``:

.. rst-class:: nlprprequest

  .. code-block:: none

    POST /nlp HTTP/1.1
    Host: myserver.mydomain
    Content-Type: application/json; charset=utf-8
    Content-Length: <length_goes_here>

    {
        "protocol": {
            "name": "nlprp",
            "version": "0.2.0"
        },
        "command":  "list_processors"
    }


*Response example*

For the specimen request above, the reply sent over TCP/IP might look like
this:

.. rst-class:: nlprpresponse

  .. code-block:: none

    HTTP/1.1 200 OK
    Date: Mon, 13 Nov 2017 09:50:59 GMT
    Server: Apache/2.4.23 (Ubuntu)
    Content-Type: application/json; charset=utf-8
    Content-Length: <length_goes_here>

    {
        "status": 200,
        "protocol": {
            "name": "nlprp",
            "version": "0.2.0"
        },
        "server_info": {
            "name": "My NLPRP server software",
            "version": "0.2.0"
        },
        "processors": [
            {
                "name": "gate_medication",
                "title": "SLAM BRC GATE-based medication finder",
                "version": "1.2.0",
                "is_default_version": true,
                "description": "Finds drug names",
                "schema_type": "unknown",
            },
            {
                "name": "python_c_reactive_protein",
                "title": "Cardinal RN (2017) CRATE CRP finder",
                "version": "0.1.3",
                "is_default_version": true,
                "description": "Finds C-reactive protein (CRP) values",
                "schema_type": "tabular",
                "sql_dialect": "mysql",
                "tabular_schema": {
                    "": [
                        {
                            "column_comment": "Variable name",
                            "column_name": "variable_name",
                            "column_type": "VARCHAR(64)",
                            "data_type": "VARCHAR",
                            "is_nullable": true
                        },
                        {
                            "column_comment": "Matching text contents",
                            "column_name": "_content",
                            "column_type": "TEXT",
                            "data_type": "TEXT",
                            "is_nullable": true
                        },
                        {
                            "column_comment": "Start position (of matching string within whole text)",
                            "column_name": "_start",
                            "column_type": "INTEGER",
                            "data_type": "INTEGER",
                            "is_nullable": true
                        },
                        {
                            "column_comment": "End position (of matching string within whole text)",
                            "column_name": "_end",
                            "column_type": "INTEGER",
                            "data_type": "INTEGER",
                            "is_nullable": true
                        },
                        {
                            "column_comment": "Text that matched the variable name",
                            "column_name": "variable_text",
                            "column_type": "TEXT",
                            "data_type": "TEXT",
                            "is_nullable": true
                        },
                        {
                            "column_comment": "Text that matched the mathematical relationship between variable and value (e.g. '=', '<=', 'less than')",
                            "column_name": "relation_text",
                            "column_type": "VARCHAR(50)",
                            "data_type": "VARCHAR",
                            "is_nullable": true
                        },
                        {
                            "column_comment": "Standardized mathematical relationship between variable and value (e.g. '=', '<=')",
                            "column_name": "relation",
                            "column_type": "VARCHAR(2)",
                            "data_type": "VARCHAR",
                            "is_nullable": true
                        },
                        {
                            "column_comment": "Matched numerical value, as text",
                            "column_name": "value_text",
                            "column_type": "TEXT",
                            "data_type": "TEXT",
                            "is_nullable": true
                        },
                        {
                            "column_comment": "Matched units, as text",
                            "column_name": "units",
                            "column_type": "VARCHAR(50)",
                            "data_type": "VARCHAR",
                            "is_nullable": true
                        },
                        {
                            "column_comment": "Numerical value in preferred units, if known",
                            "column_name": "value_mg_l",
                            "column_type": "FLOAT",
                            "data_type": "FLOAT",
                            "is_nullable": true
                        },
                        {
                            "column_comment": "Tense text, if known (e.g. 'is', 'was')",
                            "column_name": "tense_text",
                            "column_type": "VARCHAR(50)",
                            "data_type": "VARCHAR",
                            "is_nullable": true
                        },
                        {
                            "column_comment": "Calculated tense, if known (e.g. 'past', 'present')",
                            "column_name": "tense",
                            "column_type": "VARCHAR(7)",
                            "data_type": "VARCHAR",
                            "is_nullable": true
                        }
                    ]
                }
            }
        ]
    }


.. _process:

process
^^^^^^^

This command is the central NLP processing request. The important detail is
passed in the top-level ``args`` parameter, where ``args`` is an object with
the following structure:


.. rst-class:: nlprprequest

  .. list-table::
    :widths: 15 15 15 55
    :header-rows: 1

    * - Key
      - JSON type
      - Required?
      - Description

    * - ``processors``
      - Array
      - Mandatory
      - An array of objects, each with the following keys:

        - ``name`` (string): the name of an NLP processor to apply to the text
          (matching one of the names given by the server via the
          list_processors_ command).
        - ``version`` (optional string): the version of the named NLP processor
          to use. If a version is not specified explicitly, and there is a
          default version (see list_processors_), the server will use that.
        - ``args``: optional key whose value is a JSON value considered to be
          arguments to the processor (for future expansion).

    * - ``queue``
      - Boolean value (``true`` or ``false``)
      - Optional (default ``false``)
      - Controls queueing behaviour:

        - If ``true``, adds the request to the server’s processing queue, and
          returns a response giving queue information, or refuses the request.
          See the show_queue_ and fetch_from_queue_ commands below.

        - If ``false``, performs NLP immediately and returns the processing
          result.

        (Note, however, that the server can refuse to serve either immediate or
        delayed results depending on its preference.)

    * - ``client_job_id``
      - String, of maximum length 150 characters
      - Optional (if absent, an empty string will be used)
      - This is for queued processing. It is a string that the server will
        store alongside the queue request, to aid the client in identifying
        requests belonging to the same job (if it splits work across many
        requests). It is returned by the show_queue_ and fetch_from_queue_
        commands.

    * - ``include_text``
      - Boolean value (``true`` or ``false``)
      - Optional (default ``false``)
      - If ``true``, includes the source text in the reply.

    * - ``content``
      - Array
      - Mandatory
      - A list of JSON objects representing text to be parsed, with optional
        associated metadata. Each object has the following keys:

        - ``text`` (string, mandatory): The actual text to parse.
        - ``metadata`` (value, optional): The metadata will be returned
          verbatim with the results.

.. _immediate_response:

**Immediate processing**

The response to a successful non-queued process command has the following
format (on top of the basic response structure):

.. rst-class:: nlprpresponse

  .. list-table::
    :widths: 15 15 15 55
    :header-rows: 1

    * - Key
      - JSON type
      - Required?
      - Description

    * - ``client_job_id``
      - String
      - Mandatory
      - The same ``client_job_id`` as the client provided (or a blank string
        if none was provided).

    * - ``results``
      - Array
      - Mandatory
      - An array of objects of the same length as ``content``, but in arbitrary
        order, with each object having the following format:

        - ``metadata`` (optional): a copy of the text-specific ``metadata``
          provided in the request
        - ``text`` (string, optional); if ``include_text`` was true, the source
          text is included here.
        - ``processors``: array of objects in the same order as the
          ``processors`` parameter in the request, and whose keys are:

          - ``name`` (string): name of the processor (as per
            list_processors_)
          - ``title`` (string): title of the processor (as per
            list_processors_)
          - ``version`` (string): Version of the processor (as per
            list_processors_)
          - ``success`` (Boolean): ``true`` for success, ``false`` for failure.
            This allows for the possibility of text-specific failure, e.g. a
            document that crashes the NLP parser or otherwise fails
            dynamically.
          - ``errors`` (Array, optional): if ``success`` is ``false``,
            this should be present and describe the reason(s) for failure. It
            is an array of error objects, where each error is an object with at
            least the following keys:

            - ``code`` (integer or null): error code
            - ``message`` (string): brief textual description of the error
            - ``description`` (string): more detail

          - ``results``: see :ref:`Format of per-processor results
            <nlprp_format_of_per_processor_results>` below.

        Note that it is strongly advisable for clients to specify ``metadata``
        as this will be necessary for them to recover order information
        whenever ``content`` has more than one item.

.. _nlprp_format_of_per_processor_results:

**Format of per-processor results**

Remember that a single piece of source text can generate zero, one, or many NLP
matches from each processor; and that a single NLP “match” can involve highly
structured results, but typically involves one set of key/value pairs.

We now consider the
``response["results"][result_num]["processors"][processor_num]["results"]``
value. This is processor-specific.

- For a failed request, this should be an empty array, ``[]``, or an empty
  object, ``{}``. (Note that it may also be empty following success, meaning
  that the processor found nothing of interest to it.)

- If the processor does not offer a ``tabular_schema`` definition (see
  :ref:`Schema definition <nlprp_schema_definition>` above), then the format of
  ``results`` is not constrained.
  *[In NLPRP Version 0.1.0, there were no constraints, as a result.]*
  A common format is an array of objects (each object providing a key-value
  mapping of column/field names to values), like this:

  .. rst-class:: nlprpresponse

    .. code-block:: none

        "results": [
            {
                # row 1
                "column_name_1": <value_of_col_1>,
                "column_name_2": <value_of_col_2>,
                ...
            },
            {
                # row 2
                "column_name_1": <value_of_col_1>,
                "column_name_2": <value_of_col_2>,
                ...
            },
            ...
        ]

- If the processor does offer a ``tabular_schema`` definition, and that
  definition is for only a single table, then ``results`` *may* be an array of
  objects, each object representing a database row and containing a mapping
  from column names to values (exactly as above).

- If the processor offers a ``tabular_schema`` definition, the other
  permissible format is that ``results`` is an object, not an array. In this
  case, the ``results`` object maps table names (exactly as in the schema) to
  arrays of rows, like this:

  .. rst-class:: nlprpresponse

    .. code-block:: none

        "results": {
            "table_name_1": [
                {
                    # row 1
                    "column_name_1": <value_of_col_1>,
                    "column_name_2": <value_of_col_2>,
                    ...
                },
                {
                    # row 2
                    "column_name_1": <value_of_col_1>,
                    "column_name_2": <value_of_col_2>,
                    ...
                },
                ...
            ],
            "table_name_2": [
                {
                    # row 1
                    "column_name_3": <value_of_col_3>,
                    "column_name_4": <value_of_col_4>,
                    ...
                },
                {
                    # row 2
                    "column_name_3": <value_of_col_3>,
                    "column_name_4": <value_of_col_4>,
                    ...
                },
                ...
            ]
        }

  This format *must* be used by processors providing a ``tabular_schema`` and
  using more than one table.

- It is an error for the processor to offer a ``tabular_schema`` definition and
  then not abide by it (e.g. by providing table or column names not as
  described in the schema, or by returning data in non-tabular format).


**Example**

An example exchange using immediate processing follows. The request sends three
pieces of text with metadata, and requests two processors to be run on each of
them. (Neither processor takes any arguments. Since no version is specified for
the ``python_c_reactive_protein`` processor, the default version will be used.)

.. rst-class:: nlprprequest

  .. code-block:: none

    POST /nlp HTTP/1.1
    Host: myserver.mydomain
    Content-Type: application/json; charset=utf-8
    Content-Length: <length_goes_here>

    {
        "protocol": {
            "name": "nlprp",
            "version": "0.2.0"
        },
        "command":  "process",
        "args": {
            "processors": [
                {
                    "name": "gate_medication",
                    "version": "1.2.0",
                },
                {
                    "name": "python_c_reactive_protein",
                },
            ],
            "queue": false,
            "client_job_id": "My NLP job 57 for depression/CRP",
            "include_text": false,
            "content": [
                {
                    "metadata": {"myfield": "progress_notes", "pk": 12345},
                    "text": "My old man’s a dustman. He wears a dustman’s hat."
                },
                {
                    "metadata": {"myfield": "progress_notes", "pk": 23456},
                    "text": "Dr Bloggs started aripiprazole 5mg od today."
                },
                {
                    "metadata": {"myfield": "clinical_docs", "pk": 777},
                    "text": "CRP 45; concern about UTI. No longer on prednisolone. Has started co-amoxiclav 625mg tds."
                }
            ]
        }
    }

Here’s the response. The first piece of text generates no hits for either
processor. The second generates a hit for the ‘medication’ processor. The third
generates a hit for ‘CRP’ and two drugs.

.. rst-class:: nlprpresponse

  .. code-block:: none

    HTTP/1.1 200 OK
    Date: Mon, 13 Nov 2017 09:50:59 GMT
    Server: Apache/2.4.23 (Ubuntu)
    Content-Type: application/json; charset=utf-8
    Content-Length: <length_goes_here>

    {
        "status": 200,
        "protocol": {
            "name": "nlprp",
            "version": "0.2.0"
        },
        "server_info": {
            "name": "My NLPRP server software",
            "version": "0.2.0"
        },
        "client_job_id": "My NLP job 57 for depression/CRP",
        "results": [
            {
                "metadata": {"myfield": "progress_notes", "pk": 12345},
                "processors": [
                    {
                        "name": "gate_medication",
                        "title": "SLAM BRC GATE-based medication finder",
                        "version": "1.2.0",
                        "success": true,
                        "results": []
                    },
                    {
                        "name": "python_c_reactive_protein",
                        "title": "Cardinal RN (2017) CRATE CRP finder",
                        "version": "0.1.3",
                        "success": true,
                        "results": []
                    },
                ]
            },
            {
                "metadata": {"myfield": "progress_notes", "pk": 23456},
                "processors": [
                    {
                        "name": "gate_medication",
                        "title": "SLAM BRC GATE-based medication finder",
                        "version": "1.2.0",
                        "success": true,
                        "results": [
                            {
                                "drug": "aripiprazole",
                                "drug_type": "BNF_generic",
                                "dose": "5mg",
                                "dose_value": 5,
                                "dose_unit": "mg",
                                "dose_multiple": 1,
                                "route": null,
                                "status": "start",
                                "tense": "present"
                            }
                        ]
                    },
                    {
                        "name": "python_c_reactive_protein",
                        "title": "Cardinal RN (2017) CRATE CRP finder",
                        "version": "0.1.3",
                        "success": true,
                        "results": []
                    },
                ]
            },
            {
                "metadata": {"myfield": "clinical_docs", "pk": 777},
                "processors": [
                    {
                        "name": "gate_medication",
                        "title": "SLAM BRC GATE-based medication finder",
                        "version": "1.2.0",
                        "results": [
                            {
                                "drug": "prednisolone",
                                "drug_type": "BNF_generic",
                                "dose": null,
                                "dose_value": null,
                                "dose_unit": null,
                                "dose_multiple": null,
                                "route": null,
                                "status": "stop",
                                "tense": null
                            },
                            {
                                "drug": "co-amoxiclav",
                                "drug_type": "BNF_generic",
                                "dose": "625mg",
                                "dose_value": 625,
                                "dose_unit": "mg",
                                "dose_multiple": 1,
                                "route": "po",
                                "status": "start",
                                "tense": "present"
                            }
                        ]
                    },
                    {
                        "name": "python_c_reactive_protein",
                        "title": "Cardinal RN (2017) CRATE CRP finder",
                        "version": "0.1.3",
                        "results": [
                            {
                                "startpos": 1,
                                "endpos": 7,
                                "variable_name": "CRP",
                                "variable_text": "CRP",
                                "relation": "",
                                "value_text": "45",
                                "units": "",
                                "value_mg_l": 45,
                                "tense_text": "",
                                "tense": "present"
                            }
                        ]
                    },
                ]
            }
        ]
    }

Note that the two NLP processors are returning different sets of information,
in a processor-specific way.

**Queued processing**

NLP can be slow. Non-queued commands require that the server performs all the
NLP requested within the HTTP timeout period, which may not be feasible;
therefore, the protocol supports queuing. With a queued process request, the
server takes the data, says “thanks, I’m thinking about it”, and the client can
check back later. When the client checks back, the server might have data to
offer it or may still be busy.

One risk of queued commands is to the server: clients may send NLP requests
faster than the server can handle them. Therefore, the protocol allows the
server to refuse queued requests.

Another thing to note is that immediate requests may or may not require the raw
text to “touch down” somewhere on the server — what the server does is up to it
— but typically, “immediate” requests require minimal (e.g. in-memory) storage
of the raw text, whilst “queued” requests inevitably require that the server
store the text (e.g. on disk, perhaps in a database) for the lifetime of the
queue request.

**Initial successful response to process command with queued = true**

The initial response has an HTTP status code of 202 (Accepted) and a top-level
key of ``queue_id``, whose value is a string. Like this:

.. rst-class:: nlprpresponse

  .. code-block:: none

    HTTP/1.1 202 Accepted
    Date: Mon, 13 Nov 2017 09:50:59 GMT
    Server: Apache/2.4.23 (Ubuntu)
    Content-Type: application/json; charset=utf-8
    Content-Length: <length_goes_here>

    {
        "status": 202,
        "protocol": {
            "name": "nlprp",
            "version": "0.1.0"
        },
        "server_info": {
            "name": "My NLPRP server software",
            "version": "0.1.0"
        },
        "queue_id": "7586876b-49cb-447b-9db3-b640e02f4f9b"
    }


.. _show_queue:

show_queue
^^^^^^^^^^

The ``show_queue`` command allows the client to view its queue status. It has
one optional argument:


.. rst-class:: nlprprequest

  .. list-table::
    :widths: 15 15 15 55
    :header-rows: 1

    * - Key
      - JSON type
      - Required?
      - Description

    * - ``client_job_id``
      - String
      - Optional
      - An optional client job ID (see process_). If absent, all queue entries
        for this client are shown. If present, only queue entries for the
        specified ``client_job_id`` are shown.


The reply contains this extra information:

.. rst-class:: nlprpresponse

  .. list-table::
    :widths: 15 15 15 55
    :header-rows: 1

    * - Key
      - JSON type
      - Required?
      - Description

    * - ``queue``
      - Array
      - Mandatory
      - An array of objects, one for each incomplete queue entry, each with the
        following keys/values:

        - ``queue_id``: queue ID, as returned from the process_ command
        - ``client_job_id``: the client's job ID (see process_).
        - ``status``: a string; one of: ``ready``, ``busy``.
        - ``datetime_submitted``: date/time submitted, in ISO-8601 format.
        - ``datetime_completed``: date/time completed, in ISO-8601 format, or
          ``null`` if it’s not yet complete.

Specimen request:

.. rst-class:: nlprprequest

  .. code-block:: none

    POST /nlp HTTP/1.1
    Host: myserver.mydomain
    Content-Type: application/json; charset=utf-8
    Content-Length: <length_goes_here>

    {
        "protocol": {
            "name": "nlprp",
            "version": "0.1.0"
        },
        "command":  "show_queue"
    }

and corresponding response:

.. rst-class:: nlprpresponse

  .. code-block:: none

    HTTP/1.1 200 OK
    Date: Mon, 13 Nov 2017 09:50:59 GMT
    Server: Apache/2.4.23 (Ubuntu)
    Content-Type: application/json; charset=utf-8
    Content-Length: <length_goes_here>

    {
        "status": 200,
        "protocol": {
            "name": "nlprp",
            "version": "0.1.0"
        },
        "server_info": {
            "name": "My NLPRP server software",
            "version": "0.1.0"
        },
        "queue": [
            {
                "queue_id": "7586876b-49cb-447b-9db3-b640e02f4f9b",
                "client_job_id": "My NLP job 57 for depression/CRP",
                "status": "ready",
                "datetime_submitted": "2017-11-13T09:49:38.578474Z",
                "datetime_completed": "2017-11-13T09:50:00.817611Z"
            }
            {
                "queue_id": "6502b94a-2332-4f51-b2a3-337dc5d36ca0",
                "client_job_id": "My NLP job 57 for depression/CRP",
                "status": "busy",
                "datetime_submitted": "2017-11-13T09:49:39.717170Z",
                "datetime_completed": null
            }
        ]
    }


.. _fetch_from_queue:

fetch_from_queue
^^^^^^^^^^^^^^^^

Fetches a single entry from the queue, if it exists and is ready for
collection. The top-level ``args`` should contain a key ``queue_id`` containing
the queue ID.

- If the queue ID doesn’t correspond to a current queue entry, an error will be
  returned (HTTP 404 Not Found).
- If the queue entry is still busy being processed, an information code will be
  returned (HTTP 102 Processing).
- If the queue entry is ready for collection, the reply will be of the format
  for an “immediate” process request. The queue entry will be deleted upon
  collection.


.. _delete_from_queue:

delete_from_queue
^^^^^^^^^^^^^^^^^

For this command, the top-level ``args`` should be an object with the following
keys:

.. rst-class:: nlprprequest

  .. list-table::
    :widths: 15 15 15 55
    :header-rows: 1

    * - Key
      - JSON type
      - Required?
      - Description

    * - ``queue_ids``
      - Array
      - Optional
      - An array of strings, each representing a queue ID to be deleted.

    * - ``client_job_ids``
      - Array
      - Optional
      - An array of strings, each representing a client job ID for which all
        queue IDs should be deleted.

    * - ``delete_all``
      - Boolean value (``true`` or ``false``)
      - Optional (default ``false``)
      - If true, all queue entries (for this client!) are deleted.


Specimen Python 3.6+ client program
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Very briefly, run ``pip install requests crate_anon``, and then you can run
this:

.. rst-class:: nlprprequest

  .. literalinclude:: nlprp_test_client.py
     :language: python


Specimen Python 3.6+ server program
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Similarly, for a dummy server program, run ``pip install pyramid crate_anon``
and then you can run this:

.. rst-class:: nlprpresponse

  .. literalinclude:: nlprp_test_server.py
     :language: python


More on error responses
~~~~~~~~~~~~~~~~~~~~~~~

The main design question here is whether HTTP status codes should be used for
errors, or not. There are pros and cons here [#errorsviahttpstatus]_. We shall
follow best practice and encode the status both in HTTP and in the JSON.

Specific HTTP status codes not detailed above include:

================== ========================================= ==========================
Command            Situation                                 HTTP status code
================== ========================================= ==========================
Any                Success                                   200 OK
Any                Request malformed                         400 Bad Request
Any                Authorization failed                      401 Unauthorized
Any                Server bug                                500 Internal Server Error
process_           Results returned                          200 OK
process_           Request queued                            202 Accepted
process_           Server is too busy right now              503 Service Unavailable
fetch_from_queue_  No such queue entry                       404 Not Found
fetch_from_queue_  Entry still in queue and being processed  102 Processing [#http102]_
================== ========================================= ==========================


Python internal NLP interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The NLPRP server should manage per-text metadata (from the process_ command)
internally. We define a very generic Python interface for the NLPRP server to
request NLP results from a specific Python NLP processor:

.. rst-class:: nlprpresponse

  .. code-block:: python

    def nlp_process(text: str,
                    processor_args: Any = None) -> List[Dict[str, Any]]:
        """
        Standardized interface via the NLP Request Protocol (NLPRP).
        Processes text using some form of natural language processing (NLP).

        Args:
            text: the text to process
            processor_args: additional arguments supplied by the user [via a
                json.loads() call upon the processor argument value].

        Returns:
            a list of dictionaries with string keys, suitable for conversion to
            JSON using a process such as:

            .. code-block:: python

                import json
                from my_nlp_module import nlp_process
                result_dict = nlp_process("some text")
                result_json = json.dumps(result_dict)

        """
        raise NotImplementedError()

The combination of this standard interface plus the Python Package Index (PyPI)
should allow easy installation of Python NLP managers (by Python package name
and version). The NLPRP server should be able to import a ``nlp_process`` or
equivalent function from the top-level package.


Existing code of relevance
~~~~~~~~~~~~~~~~~~~~~~~~~~

The CRATE toolchain has Python handlers for firing up external NLP processors
including GATE and other Java-based tools, and piping text to them; similarly
for its internal Python code. From the Cambridge perspective we are likely to
extend and use CRATE to send data to the NLP API/service and manage results,
but it is also potentially extensible to serve as the NLP API server.


Aspects of server function that are not part of the NLPRP specification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following are implementation details that are at the server's discretion:

- authentication_
- authorization_
- accounting (logging, billing, size/frequency restrictions)
- containerization, parallel processing, message queue details 


Abbreviations used in this section
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

======= =======================================================================
EMR     electronic medical records
HTTP    hypertext transport protocol
HTTPS   secure HTTP
IP      Internet protocol
ISO     International Organization for Standardization
JSON    JavaScript Object Notation
KVP     key–value pair
NHS     UK National Health Service
NLP     natural language processing
NLPRP   NLP Request Protocol
PyPI    The Python Package Index; https://pypi.python.org/
REST    Representational state transfer
TCP     transmission control protocol
UK      United Kingdom
URL     uniform resource locator
UTC     Universal Coordinated Time
UTF-8   Unicode Transformation Format, 8-bit
XML     Extensible Markup Language
======= =======================================================================


NLPRP things to do and potential future requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. todo:: NLPRP: consider supra-document processing requirements

Corpus (supra-document) processing:

- There may be future use cases where the NLP processor must simultaneously
  consider more than one document (a "corpus" of documents, in GATE_
  terminology). This is not currently supported. However, batch processing is
  currently supported.


NLPRP history
~~~~~~~~~~~~~

**v0.0.1**

- Started 13 Nov 2017; Rudolf Cardinal.

**v0.0.2**

- RNC
- Minor changes 18 July 2018 following discussion with SLAM/KCL team.

**v0.1.0**

- Amendments 4 Oct 2018, RNC/IR/FS/JK/AR.
- Authentication moved out of the API.
- Authorization moved out of the API.
- The server may "fail" requests at the HTTP level or at the subsequent NLPRP
  processing stage (i.e. failures may or may not include an NLPRP response
  object).
- Compression at HTTP level discussed; servers should accept ``gzip``
  compression from the client.
- Order of ``results`` object changed to arbitrary (to facilitate parallel
  processing).
- ``echorequest``/``echo`` parameters removed; this was pointless as all HTTP
  calls have an associated reply, so the client should never fail to know what
  was echoed back.
- ``is_default_version`` argument to the list_processors_ reply, and
  ``version`` argument to process_.
- Comment re future potential use case for corpus-level processing
- Signalling mechanism for dynamic failure via the ``success`` and
  ``errors`` parameters to the response (see `immediate response
  <immediate_response>`_).
- Ability for the client to pass a ``client_job_id`` to
  the queued processing mode, so it can add many requests to the same job and
  retrieve this data as part of ``show_queue``. Similar argument to
  delete_from_queue_.
- Consideration of processor version control and how this is managed in
  practice (e.g. Python modules; GATE apps) isn't part of the API; removed
  from "to-do" list.

**v0.2.0**

- 4-6 Aug 2019, RNC.
- Processors can describe their output format: ``schema_type`` and
  ``tabular_schema`` attribute in the response to the list_processors_ command,
  with associated ``sql_dialect`` options.
- Corresponding constraints on the results format for processors that provide a
  tabular schema.


===============================================================================

.. rubric:: Footnotes

.. [#getvspost]
    http://blog.teamtreehouse.com/the-definitive-guide-to-get-vs-post

.. [#rfc7231]
    https://tools.ietf.org/html/rfc7231#section-4.3.3

.. [#soap]
    https://en.wikipedia.org/wiki/SOAP

.. [#errorsviahttpstatus]

    See:

    - https://stackoverflow.com/questions/942951/rest-api-error-return-good-practices
    - https://cloud.google.com/storage/docs/json_api/v1/status-codes
    - https://blogs.mulesoft.com/dev/api-dev/api-best-practices-response-handling/
    - https://developer.twitter.com/en/docs/basics/response-codes
    - http://www.iana.org/assignments/http-status-codes/http-status-codes.xhtml
    - https://blog.runscope.com/posts/6-common-api-errors

.. [#http102]

    See:

    - https://stackoverflow.com/questions/9794696/how-do-i-choose-a-http-status-code-in-rest-api-for-not-ready-yet-try-again-lat
    - https://tools.ietf.org/html/rfc2518#section-10.1
