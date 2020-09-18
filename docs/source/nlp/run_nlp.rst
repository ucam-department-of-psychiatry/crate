..  crate_anon/docs/source/nlp/run_nlp.rst

..  Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).
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

.. _NetLimiter: https://www.netlimiter.com/
.. _requests: http://docs.python-requests.org
.. _ThrottlingFactory: https://twistedmatrix.com/documents/current/api/twisted.protocols.policies.ThrottlingFactory.html
.. _treq: https://treq.readthedocs.io/
.. _trickle: https://www.usenix.org/legacy/event/usenix05/tech/freenix/full_papers/eriksen/eriksen.pdf
.. _Twisted: https://twistedmatrix.com/
.. _txrequests: https://pypi.org/project/txrequests/


Run the NLP
-----------

Now you've created and edited your config file, you can run the NLP process in
one of the following ways:

.. code-block:: bash

    crate_nlp --nlpdef NLP_NAME --incremental
    crate_nlp --nlpdef NLP_NAME --full
    crate_nlp_multiprocess --nlpdef NLP_NAME --incremental
    crate_nlp_multiprocess --nlpdef NLP_NAME --full

where `NLP_NAME` is something you’ve configured in the :ref:`NLP config file
<nlp_config>` (e.g. a drug-parsing NLP program or the GATE demonstration
name/location NLP app). Use

The ‘multiprocess’ versions are faster (if you have a multi-core/-CPU
computer). The ‘full’ option destroys the destination database and starts
again. The ‘incremental’ one brings the destination database up to date
(creating it if necessary). The default is ‘incremental’, for safety reasons.

Get more help with

.. code-block:: bash

    crate_nlp --help


.. _crate_nlp:

crate_nlp
~~~~~~~~~

This runs a single-process NLP controller.

Options:

..  literalinclude:: _crate_nlp_help.txt
    :language: none


Current NLP processors
~~~~~~~~~~~~~~~~~~~~~~

NLP processors (from ``crate_nlp --describeprocessors``):

..  literalinclude:: _crate_nlp_describeprocessors.txt
    :language: none


.. _crate_nlp_multiprocess:

crate_nlp_multiprocess
~~~~~~~~~~~~~~~~~~~~~~

This program runs multiple copies of ``crate_nlp`` in parallel.

Options:

..  literalinclude:: _crate_nlp_multiprocess_help.txt
    :language: none


Limiting the network bandwidth used by cloud NLP
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Cloud-based NLP may involve sending large quantities of text (de-identified and
encrypted en route) to a distant server. If you have limited network bandwidth,
you may want to cap the bandwidth used by CRATE (at the price of speed).

**Under Linux,** use trickle_. Here's how:

.. code-block:: bash

    # Install with e.g. "sudo apt install trickle", then see "man trickle".
    # Source code is at https://github.com/mariusae/trickle.
    # Example with limits of 500 KB/s download, 200 KB/s upload:
    trickle -s -d 500 -u 200 crate_nlp <OPTIONS>

**Under Windows,** use NetLimiter_. The rationale is as follows.

Under Windows, the choice is less obvious. A commercial opton is NetLimiter_,
but there is no direct equivalent of trickle_. Python options require quite a
bit of network code redesign; e.g.

- https://stackoverflow.com/questions/3488616/bandwidth-throttling-in-python
- https://stackoverflow.com/questions/17691231/how-to-limit-download-rate-of-http-requests-in-requests-python-library
- https://stackoverflow.com/questions/20247354/limiting-throttling-the-rate-of-http-requests-in-grequests
- https://stackoverflow.com/questions/13047458/bandwidth-throttling-using-twisted

but with the exception of rewriting network code to use Twisted_ rather than
requests_, none of these open-source methods address the general-purposes
bandwidth limitation challenge addressed by trickle_. The best option might be
txrequests_ or treq_ plus bandwidth limitation via Twisted_ through its
ThrottlingFactory_, but this doesn't look entirely simple (see links above).
Even with that, it'd be hard to coordinate bandwidth limits across multiple
processes.

Therefore, in favour of NetLimiter_:

- it's cheap (~$30/licence in 2019);
- it provides a per-host unlimited-duration licence;
- if you're using Windows you're already in the domain of commercial software;
- the cloud NLP facility of CRATE is the sort of thing you're likely to run on
  one big computer rather than lots of computers (so one licence should
  suffice);
- its filters are very flexible (including time-of-day restrictions and the
  ability to group applications);
- the alternatives would involve substantial development effort for lesser
  benefit;

... so NetLimiter_ seems like the most cost-effective option.
