.. crate_anon/docs/source/nlp/nlprp.rst

..  Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).
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

.. _JSON: https://www.json.org/
.. _RESTful: https://en.wikipedia.org/wiki/Representational_state_transfer
.. _Semantic Versioning: http://www.semver.org/
.. _ISO-8601: https://en.wikipedia.org/wiki/ISO_8601


Natural Language Processing Request Protocol (NLPRP): DRAFT
-----------------------------------------------------------

**Version 0.0.2**

.. contents::
   :local:

Authors
~~~~~~~

- Rudolf Cardinal, University of Cambridge
- [and all others welcome!]


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

The underlying application layer is HTTPS (encrypted HTTP), over TCP/IP.

Request
~~~~~~~

Request format
^^^^^^^^^^^^^^

Requests are always transmitted using the HTTP ``POST`` method.

- Rationale:

  (1) Some calls modify state on the server, making ``GET`` inappropriate.
  (2) Some requests will be large, making ``GET`` URL encoding inappropriate.
  (3) Many requests involve sensitive data, which should not be encoded into
      URLs via ``GET``.
  (4) Therefore, all requests are via ``POST`` [#getvspost]_.

- The POST method itself is broad [#rfc7231]_.

The request content is in JSON_, with media type ``application/json``. The
encoding can be specified, and will be assumed to be UTF-8 if not specified.

- Rationale: we need a structured notation supporting list types, key–value
  pair (KVP) types, a null notation, and arbitrary nesting. JSON fulfils this,
  is simple (and thus fast), is legible to humans, and is widely supported
  under many programming languages. Other formats such as XML require
  considerably more complex parsing and are slower [#soap]_.

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

Where versions are passed, they are in `Semantic Versioning`_ 2.0.0
format. Semantic versions are strings using a particular format
(e.g. ``"1.2.0"``), referred to as a Version henceforth.

Where date/time values are passed, they are in `ISO-8601`_ format
and must include all three of: date, time, timezone. (The choice of timezone is
immaterial; servers may choose to use UTC throughout.)

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

    * - ``authentication``
      - Object
      - Optional
      - Authentication details, for hosts not supporting anonymous requests.
        Keys for username/password authentication:

        - ``username`` (string): Username.
        - ``password`` (string): Password.

    * - ``echo_request``
      - Value
      - Optional
      - If present, the value of this field will be part of the reply as the
        echo value.

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

Response
~~~~~~~~

Response format
^^^^^^^^^^^^^^^

The request is returned over HTTP as media type ``application/json``. The
encoding *should** be specified (e.g. ``application/json; charset=utf-8``, and
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

    * - ``echo``
      - Value
      - Optional
      - If the ``echorequest`` key was present in the request, its associated
        value is returned as the value for ``echo``.


NLPRP commands
~~~~~~~~~~~~~~

.. _list_processors:

list_processors
^^^^^^^^^^^^^^^

No additional parameters are required.

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
        - ``description`` (string): a description of the processor.

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
            "version": "0.0.1"
        },
        "authentication": {
            "username": "myuser",
            "password": "mypassword"
        },
        "echorequest": {
            "my_request_reference": 12347,
            "some_other_data_as_list": [3, 6]
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
            "version": "0.0.1"
        },
        "server_info": {
            "name": "My NLPRP server software",
            "version": "0.0.1"
        },
        "echo": {
            "my_request_reference": 12347,
            "some_other_data_as_list": [3, 6]
        },
        "processors": [
            {
                "name": "gate_medication",
                "title": "SLAM BRC GATE-based medication finder",
                "version": "1.2.0",
                "description": "Finds drug names"
            },
            {
                "name": "python_c_reactive_protein",
                "title": "Cardinal RN (2017) CRATE CRP finder",
                "version": "0.1.3",
                "description": "Finds C-reactive protein (CRP) values"
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
          list_processors command).
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

    * - ``results``
      - Array
      - Mandatory
      - An array of objects in the same order as content, with each object
        having the following format:

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
          - ``results``: array of objects (typically one per NLP result) each
            with a format defined by the processor itself.

Remember that a single piece of source text can generate zero, one, or many NLP
matches from each processor; and that a single NLP “match” can involve highly
structured results, but typically involves one set of key/value pairs.

An example exchange using immediate processing follows. The request sends three
pieces of text with metadata, and requests two processors to be run on each of
them. (Neither processor takes any arguments.)

.. rst-class:: nlprprequest

  .. code-block:: none

    POST /nlp HTTP/1.1
    Host: myserver.mydomain
    Content-Type: application/json; charset=utf-8
    Content-Length: <length_goes_here>

    {
        "protocol": {
            "name": "nlprp",
            "version": "0.0.1"
        },
        "authentication": {
            "username": "myuser",
            "password": "mypassword"
        },
        "echorequest": {
            "my_request_reference": 7171,
            "some_other_data": "hello",
        },
        "command":  "process",
        "args": {
            "processors": [
                {
                    "name": "gate_medication",
                },
                {
                    "name": "python_c_reactive_protein",
                },
            ],
            "queue": false,
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
            "version": "0.0.1"
        },
        "server_info": {
            "name": "My NLPRP server software",
            "version": "0.0.1"
        },
        "echo": {
            "my_request_reference": 7171,
            "some_other_data": "hello",
        },
        "results": [
            {
                "metadata": {"myfield": "progress_notes", "pk": 12345},
                "processors": [
                    {
                        "name": "gate_medication",
                        "title": "SLAM BRC GATE-based medication finder",
                        "version": "1.2.0",
                        "results": []
                    },
                    {
                        "name": "python_c_reactive_protein",
                        "title": "Cardinal RN (2017) CRATE CRP finder",
                        "version": "0.1.3",
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
                                "tense":  null
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
            "version": "0.0.1"
        },
        "server_info": {
            "name": "My NLPRP server software",
            "version": "0.0.1"
        },
        "echo": {
            "my_request_reference": 7171,
            "some_other_data": "hello",
        },
        "queue_id": "7586876b-49cb-447b-9db3-b640e02f4f9b"
    }


.. _show_queue:

show_queue
^^^^^^^^^^

The ``show_queue`` command allows the client to view its queue status. It has
no arguments.

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
            "version": "0.0.1"
        },
        "authentication": {
            "username": "myuser",
            "password": "mypassword"
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
            "version": "0.0.1"
        },
        "server_info": {
            "name": "My NLPRP server software",
            "version": "0.0.1"
        },
        "queue": [
            {
                "queue_id": "7586876b-49cb-447b-9db3-b640e02f4f9b",
                "status": "ready",
                "datetime_submitted": "2017-11-13T09:49:38.578474Z",
                "datetime_completed": "2017-11-13T09:50:00.817611Z",
            }
            {
                "queue_id": "6502b94a-2332-4f51-b2a3-337dc5d36ca0",
                "status": "busy",
                "datetime_submitted": "2017-11-13T09:49:39.717170Z",
                "datetime_completed": null,
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

In this context, note in particular that the ``echo`` parameter is used for the
same request* (so if you run a queued process command echoing ``"echo1"``, then
a ``fetch_from_queue`` command echoing ``"echo2"``, you will get ``"echo2"``
back with the ``fetch_from_queue`` command), but the per-text *metadata* is
preserved from initial queueing to final retrieval (so that’s the place to put
information you require to file your results!).


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

    * - ``delete_all``
      - Boolean value (``true`` or ``false``)
      - Optional (default ``false``)
      - If true, all queue entries (for this client!) are deleted.


Specimen Python 3.5+ client program
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Very briefly, run ``pip install requests``, and then you can do:

.. rst-class:: nlprprequest

  .. code-block:: python

    #!/usr/bin/env python

    import json
    import logging
    import requests
    from typing import Dict, Any

    log = logging.getLogger(__name__)

    def get_response(url: str, command: str, username: str = "", password: str = "",
                     command_args: Any = None) -> Dict[str, Any]:
        """
        Illustrate sending to/receiving from an NLPRP server.
        """
        # -------------------------------------------------------------------------
        # Build request and send it
        # -------------------------------------------------------------------------
        request_dict = {
            "protocol": {
                "name": "nlprp",
                "version": "0.0.1"
            },
            "authentication": {
                "username": username,
                "password": password
            },
            "command": command,
            "args": json.dumps(command_args),
        }
        request_json = json.dumps(request_dict)
        log.debug("Sending to {!r}:\n{}".format(url, request_json))
        r = requests.post(url, json=request_json)
        # -------------------------------------------------------------------------
        # Process response
        # -------------------------------------------------------------------------
        log.debug("Reply had status code {} and was:\n{}".format(
            r.status_code, r.text))
        try:
            response_dict = r.json()
        except json.decoder.JSONDecodeError:
            log.warning("Reply was not JSON")
            raise
        log.debug("Response JSON decoded to: {!r}".format(response_dict))
        return response_dict


    if __name__ == "__main__":
        logging.basicConfig(level=logging.DEBUG)
        get_response(url=SOME_URL, username=SOME_USER, password=SOME_PW,
                     command="list_processors")


More on error responses
~~~~~~~~~~~~~~~~~~~~~~~

The main design question here is whether HTTP status codes should be used for
errors, or not. There are pros and cons here [#errorsviahttpstatus]_. We shall follow best practice
and encode the status both in HTTP and in the JSON.

Specific HTTP status codes not detailed above include:

================== ========================================= ========================
Command            Situation                                 HTTP status code
================== ========================================= ========================
Any                Success                                   200 OK
Any                Authorization failed                      401 Unauthorized
process_           Results returned                          200 OK
process_           Request queued                            202 Accepted
process_           Server is too busy right now              503 Service Unavailable
fetch_from_queue_  No such queue entry                       404 Not Found
fetch_from_queue_  Entry still in queue and being processed  102 Processing [#http102]_
================== ========================================= ========================


Python internal NLP interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The NLPRP server should manage per-request metadata (``echorequest``/``echo``)
and per-text metadata (from the process_ command) internally. We define a very
generic Python interface for the NLPRP server to request NLP results from a
specific Python NLP processor:

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

.. todo::
    NLPRP: Any package/module/function naming convention not worked out fully;
    ?required or not.

.. todo::
    NLPRP: What’s the standard for GATE app version control / libraries?

Existing code of relevance
~~~~~~~~~~~~~~~~~~~~~~~~~~

The CRATE toolchain has Python handlers for firing up external NLP processors
including GATE and other Java-based tools, and piping text to them; similarly
for its internal Python code. From the Cambridge perspective we are likely to
extend and use CRATE to send data to the NLP API/service and manage results,
but it is also potentially extensible to serve as the NLP API server.

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

NLPRP things to do
~~~~~~~~~~~~~~~~~~

.. todo:: NLPRP: remove echo; pointless (it’s metadata that we want)
.. todo:: NLPRP: (not part of API) potentially containerization (Docker etc.) on the server side
.. todo:: NLPRP: (not part of API) CPU time logs/billing/security on the server side
.. todo:: NLPRP: add ‘limits’ part to server info (e.g. max_texts_per_request, max_processors_per_request, max_texts_times_processors_per_request) and a failing code for “too much work requested”
.. todo:: NLPRP: … rename list_processors to server_info, and add limits there?
.. todo:: NLPRP: build in cardinal_pythonlib.nvprp
.. todo:: NLPRP: should all NVP processors offer up a database schema (or something similar)?


NLPRP history
~~~~~~~~~~~~~

**v0.0.1**

- Started 13 Nov 2017; Rudolf Cardinal.

**v0.0.2**

- Minor changes 18 July 2018 following discussion with SLAM/KCL team.
- CURRENT WORKING VERSION.

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
