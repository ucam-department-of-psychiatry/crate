.. crate_anon/docs/source/misc/semehr.rst

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

.. _Docker: https://www.docker.com
.. _Docker Compose: https://docs.docker.com/compose/
.. _Docker Desktop for Windows: https://docs.docker.com/docker-for-windows/install/
.. _Elasticsearch: https://www.elastic.co/products/elasticsearch
.. _Elasticsearch Docker: https://www.elastic.co/guide/en/elasticsearch/reference/current/docker.html
.. _httpd: https://hub.docker.com/_/httpd


Using SemEHR
============

.. contents::
   :local:


SemEHR is a tool to make apparent semantic data from notes in electronic health
records. See:

- Wu H, Toti G, Morley KI, Ibrahim ZM, Folarin A, Jackson R, Kartoglu I,
  Agrawal A, Stringer C, Gale D, Gorrell G, Roberts A, Broadbent M, Stewart R,
  Dobson RJB (2018).
  SemEHR: A general-purpose semantic search system to surface semantic data
  from clinical notes for tailored care, trial recruitment, and clinical
  research.
  *J Am Med Inform Assoc* 25: 530-537.
  https://www.ncbi.nlm.nih.gov/pubmed/29361077

- https://github.com/CogStack/CogStack-SemEHR

- It uses Elasticsearch_.

Here we summarize quick ways to get SemEHR operational.


Background on Docker
--------------------

Docker_ delivers software in "containers", which package up code and its
dependencies. The container is portable to any Docker-enabled machine. It can
be build automatically from a ``Dockerfile``, which is a text description of
the container.

With regard to operating systems:

- There is a "host OS" ("container host"), which is the operating system that
  the computer running Docker is using.

- Containers can have a "container OS" ("base OS"), which is what the software
  in the container sees. If the container is very different (e.g. Linux
  container on Windows host), then virtualization is used (e.g. running
  virtualized Ubuntu on Windows, and Docker containers in or on top of that).
  If the container is similar (e.g. a container of one flavour of Linux running
  on another), then the underlying kernel can be used, which is faster. If the
  container wants to use the same OS as the host OS (e.g. Ubuntu container
  running on Ubuntu machine) then a "no-OS" container can be used, which is
  also fast. Most descriptions of Docker involve Linux containers on a Linux
  host.

- The container uses only the kernel from the host OS (but it can therefore
  run one Linux distribution on top of another's kernel).

See

- https://docs.docker.com/get-started/

- https://docs.docker.com/engine/faq/

- http://www.floydhilton.com/docker/2017/03/31/Docker-ContainerHost-vs-ContainerOS-Linux-Windows.html

- https://docs.docker.com/engine/reference/builder/

- https://stackoverflow.com/questions/18786209/what-is-the-relationship-between-the-docker-host-os-and-the-container-base-image

`Docker Compose`_ is a tool for running multi-container Docker applications.
It uses a control file typically called ``docker-compose.yml`` to describe the
containers, which can then be started with the command ``docker-compose up``
and stopped with ``docker-compose down``.


Installing Docker for Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Install the software.

  .. code-block:: bash

    sudo apt update
    sudo apt-get remove docker docker-engine docker.io

    # Docker
    sudo apt install docker.io

    # If you want it to start automatically:
    sudo systemctl start docker
    sudo systemctl enable docker

    # Docker Compose. Note that "sudo apt install docker-compose" may go wrong.
    sudo apt install curl
    sudo curl -L "https://github.com/docker/compose/releases/download/1.23.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose

- Edit ``/etc/group`` to add your user to the ``docker`` group. Log out and log
  in again to pick up the change. (Otherwise you will get the error ``Got
  permission denied while trying to connect to the Docker daemon socket``.)

- Check it's working:

  .. code-block:: bash

    groups  # Which groups am I in?
    # ... Should include "docker". If not, try "groups <MYUSERNAME>". If the
    # two differ, reboot and retry. If "docker" is in neither, you have not
    # edited /etc/group properly.

    docker --version
    docker version  # More detailed; should show client and server version.

    docker-compose --version
    docker-compose version  # More detailed.


Installing Docker for Windows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install `Docker Desktop for Windows`_.


SemEHR tutorial via Docker on Ubuntu
------------------------------------

This is based on https://semehr.cogstack.systems/tutorials.html.

Prerequisites:

- Docker and Docker Compose, as above.
- A BioYODIE installation (see links in tutorial)

Set some environment variables:

..  literalinclude:: semehr_set_envvars.sh
    :language: bash

Make some amendments:

..  literalinclude:: semehr_setup_demo.sh
    :language: bash

Now start Elasticsearch:

..  literalinclude:: semehr_start_elasticsearch.sh
    :language: bash

Now fire up another terminal, enter the same variable definitions as above, and
fix an Elasticsearch problem:

..  literalinclude:: semehr_fix_watermark.sh
    :language: bash

Now in that second terminal, run SemEHR:

..  literalinclude:: semehr_run_semehr.sh
    :language: bash

Browse to http://127.0.0.1:8080/SemEHR.html and try searching for patient
``P001``. Try also http://127.0.0.1:8200/_cat/indices/, which should show
current indices (you expect one called ``eprdoc``).

Once the Elasticsearch container group is  happy, you can (if you want) shut it
down (``Ctrl-C``) and restart it in the background:

.. code-block:: bash

    docker-compose -f "${ELASTICSEARCH_COMPOSE}" up -d

    # And when you want to shut down Elasticsearch:
    docker-compose -f "${ELASTICSEARCH_COMPOSE}" down


Notes on Docker
---------------

Docker information and debugging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- You can explore what's going on:

  .. code-block:: bash

    docker-compose -f <COMPOSEFILE> images
    docker-compose -f <COMPOSEFILE> top
    docker images
    docker container ls
    docker stats  # Ctrl-C to finish
    docker ps

- If things are going wrong, you can start a shell in a running container (see
  e.g. https://phase2.github.io/devtools/common-tasks/ssh-into-a-container/),
  such as with:

  .. code-block:: bash

    docker ps  # get container ID
    docker exec -it <CONTAINER_ID> /bin/bash

  Note that the Elasticsearch containers are meant to start up and stay up, but
  the SemEHR container is meant to run (sending data to Elasticsearch), then
  stop.

- To monitor network traffic:

  .. code-block:: bash

    # Run Wireshark
    # (a) from Docker (e.g. https://hub.docker.com/r/manell/wireshark/):
    #
    # docker run -ti --net=host --privileged -v $HOME:/root:ro -e XAUTHORITY=/root/.Xauthority -e DISPLAY=$DISPLAY manell/wireshark
    #
    # (b) Natively:

    wireshark

    # Now use Wireshark filters e.g. to debug browsing to http://172.17.0.1:
    # (ip.dst == 172.17.0.1 || ip.src == 172.17.0.1) && http

- To trash a Docker system thoroughly:

  .. code-block:: bash

    # DANGER: destroys everything it can from Docker.
    docker stop $(docker ps -q)
    docker container rm $(docker container ls -a -q)
    docker image rm $(docker image ls -a -q)
    docker volume rm $(docker volume ls -q)
    docker network rm $(docker network ls -q)
    docker system prune -a


Docker networking
~~~~~~~~~~~~~~~~~

- Docker always creates a default network interface (called ``docker0``; run
  ``ifconfig`` to see them), plus a default Docker network whose name is
  ``bridge`` (run ``docker network inspect bridge`` to see details). You can
  see what Docker does in terms of routing by running ``sudo iptables -t nat
  -S``. The default Docker network appears as the private network
  ``172.17.0.0``.

- Docker may set up multiple networks. View them with:

  .. code-block:: bash

    docker network ls
    docker network inspect $(docker network ls -q)

- To get a container's IP address (as seen by other processes on the host
  machine), use

  .. code-block:: bash

    docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <CONTAINER_NAME_OR_ID>

  You can see more information on a container with

  .. code-block:: bash

    docker inspect <CONTAINER_NAME_OR_ID>

- Within a Docker Compose container collection (I can't find an established
  noun for one of these, so will call it a "composition"), applications can use
  each other's service names as IP names -- so, for example, containers can
  talk to the the web container via ``http://web/...`` and to the database
  container as ``postgres://db:5432``. However, this naming system does not
  extend to the "outside world" of the host machine (verified empirically), or
  to Docker containers outside the composition.

- Compositions may define their own networks. But if they don't (as SemEHR
  doesn't as of 2019-11-11):

  - Docker Compose will create a network whose name is that of the directory
    containing the ``.yml`` file (minus punctuation), plus ``_default`` --
    thus, for SemEHR, this is ``tutorial1composefiles_default``. In our tests
    this network is typically ``172.21.0.0``.

  - Individual containers may be exposed via multiple IP addresses. For
    example, the ``es01`` container's exposed port 8200 (see below) is
    accessible via two gateways:

    .. code-block:: bash

        # With the Elasticsearch composition running:
        # Get IP address of "es01" container:
        docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' es01
        # ... currently 172.21.0.2

        # Ping it
        ping 172.21.0.2
        # ... OK

        # Which ports are open?
        nmap 172.21.0.2  # es01 container
        # ... port 9200 is open

        # (Not shown) Establish that the "es02" container is 172.21.0.4,
        # and the web ("tutorial1composefiles_web_1") container is 172.21.0.3.

        nmap 172.21.0.4  # es02 container
        # ... port 9200 is open

        nmap 172.21.0.3  # tutorial1composefiles_web_1 container
        # ... port 80 is open

        # Now, there is a special one at 172.21.0.1:
        docker network inspect $(docker network ls -q) | less
        # ... shows that 172.21.0.1 is the gateway for the network named
        #     tutorial1composefiles_default

        nmap 172.21.0.1  # gateway for this composition's network
        # ... ports 22, 8080, 8200 are open.
        # ... reducing to port 22 when the Elasticsearch composition shuts down

        # What about 172.17.0.1, the gateway for the Docker default bridge
        # network?
        nmap 172.17.0.1  # gateway for default Docker network
        # ... ports 22, 8080, 8200 are open.
        # ... reducing to port 22 when the Elasticsearch composition shuts down

        # What about the host machine itself?
        nmap localhost  # or nmap 127.0.0.1
        # ... in my case: stuff including 8080, 8200
        # ... reducing to stuff not including 8080, 8200 when ES container down

        curl http://172.17.0.1:8080  # gives SemEHR web page
        curl http://172.21.0.1:8080  # gives SemEHR web page

        curl http://172.17.0.1:8200  # gives Elasticsearch JSON result
        curl http://172.21.0.1:8200  # gives Elasticsearch JSON result

        # ssh into the es01 container:
        docker exec -it es01 /bin/bash
        # then try: find / -type f -name "*.log"

- Therefore, the SemEHR container can currently access the Elasticsearch
  container via any of:

  .. code-block:: none

    http://172.17.0.1:8200
    http://172.21.0.1:8200
    http://localhost:8200
    http://127.0.0.1:8200

See:

- https://docs.docker.com/compose/networking/
- https://stackoverflow.com/questions/50282792/how-does-docker-network-work


Docker debugging container
~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's create a container that mimics the SemEHR "runner", in that it
is part of our created network, but not in the Elasticsearch composition.

In ``debugger.yml``:

.. code-block:: yaml

    version: '3.3'

    services:
      debugger:
        image: praqma/network-multitool
        container_name: debugger
    networks:
      default:
        external:
          name: semehrnet

.. code-block:: bash

    docker-compose -f debugger.yml up -d

And in a separate command line:

.. code-block:: bash

    docker exec -it debugger /bin/bash

Via ``ping``, ``nmap``, and ``curl``, we see that the correct URL is
``http://es01:9200/`` (and ``http://web/`` or ``http://web:80/``).


Notes on the SemEHR docker setup
--------------------------------

- SemEHR sets up a background Docker application via Docker Compose. This
  has three containers:

  - ``web`` uses the httpd_ image, which serves content from its
    ``/usr/local/apache2/htdocs/`` directory on port 80. The Compose file
    maps some SemEHR data to this directory, and exposes the web server on
    port **8080**.

  - ``es01`` uses an `Elasticsearch Docker`_ image, which offers Elasticsearch
    on port 9200. SemEHR maps that to port **8200**.

  - ``es02`` is another Elasticsearch image. The Docker Compose configuration
    allows them to talk to each other, as per the `Elasticsearch Docker`_
    instructions.

  This application is intended to run in the background. It provides
  Elasticsearch indexing and a web interface.

- It then offers another container to parse SemEHR data. This application is
  intended to run and stop once it's processed everything.

  - Its config file,
    ``CogStack-SemEHR/tutorials/mtsamples-cohort/semehr_settings.json``,
    governs how this container finds the Elasticsearch container.

    - The JSON config file format is described at
      https://github.com/CogStack/CogStack-SemEHR/wiki.

    - The Elasticsearch URL (including the IP address of the other Docker
      container) is configured by ``es_host`` and ``es_doc_url``.

  - It writes to ``semehr.log`` in the same directory.


Troubleshooting SemEHR
----------------------

Persistent wrong Docker paths
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you started a container based on a ``.yml`` file with wrong directories, the
settings can persist. Try ``docker container ls`` followed by ``docker
container rm ...``, but if there are no containers listed yet the problem still
persists, try ``docker image ls`` followed by ``docker image rm <IMAGE_ID>``.
Then the container will be rebuilt when you next restart it. If that doesn't
work, try ``docker images purge`` and ``docker system prune -a``, delete the
tutorial directory, and start again.

- Note that under Ubuntu, Docker data is in ``/var/lib/docker``.

- These were the errors:

  .. code-block:: none

    ERROR: for es01  Cannot create container for service es01: failed to mount local volume: mount /semehr_tutorial1/CogStack-SemEHR/tutorials/working_dCreating tutorial1composefiles_web_1 ... error
    ERROR: for tutorial1composefiles_web_1  Cannot create container for service web: failed to mount local volume: mount /semehr_tutorial1/CogStack-SemECreating es02 ... error
    ERROR: for es02  Cannot create container for service es02: failed to mount local volume: mount /semehr_tutorial1/CogStack-SemEHR/tutorials/working_data/docker_es02:/var/lib/docker/volumes/tutorial1composefiles_esdata02/_data, flags: 0x1000: no such file or directory
    ERROR: for es01  Cannot create container for service es01: failed to mount local volume: mount /semehr_tutorial1/CogStack-SemEHR/tutorials/working_data/docker_es01:/var/lib/docker/volumes/tutorial1composefiles_esdata01/_data, flags: 0x1000: no such file or directory
    ERROR: for es02  Cannot create container for service es02: failed to mount local volume: mount /semehr_tutorial1/CogStack-SemEHR/tutorials/working_data/docker_es02:/var/lib/docker/volumes/tutorial1composefiles_esdata02/_data, flags: 0x1000: no such file or directory
    ERROR: for web  Cannot create container for service web: failed to mount local volume: mount /semehr_tutorial1/CogStack-SemEHR/UI/patient_phenome_ui:/var/lib/docker/volumes/tutorial1composefiles_semehr_phenome_ui_folder/_data, flags: 0x1000: no such file or directory

- Show volumes with ``docker volume ls``:

  .. code-block:: none

    DRIVER              VOLUME NAME
    local               tutorial1composefiles_esdata01
    local               tutorial1composefiles_esdata02
    local               tutorial1composefiles_semehr_phenome_ui_folder

- Show details on one with e.g. ``docker volume inspect
  tutorial1composefiles_esdata01``:

  .. code-block:: none

    [
        {
            "CreatedAt": "2019-11-07T16:04:18Z",
            "Driver": "local",
            "Labels": {
                "com.docker.compose.project": "tutorial1composefiles",
                "com.docker.compose.volume": "esdata01"
            },
            "Mountpoint": "/var/lib/docker/volumes/tutorial1composefiles_esdata01/_data",
            "Name": "tutorial1composefiles_esdata01",
            "Options": {
                "device": "/semehr_tutorial1/CogStack-SemEHR/tutorials/working_data/docker_es01",
                "o": "bind",
                "type": "none"
            },
            "Scope": "local"
        }
    ]

This was on 2019-11-08 after wiping everything I'd thought of. So it seems that
the thing that is being persisted/cached is the volume.

A few calls to ``docker volume rm ...`` later... and it's happy.

Lesson: containers and volumes are independent!

Still problems, though. Complete purge, as above.


Errors relating to a full disk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you see ``INTERNAL ERROR: cannot create temporary directory!``, your disk
is probably full. (Lots of rubbish in ``/var/spool/mail/root``, for example?)


Elasticsearch complains about vm.max_map_count
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the Elasticsearch containers fail to start and give the error message
``max virtual memory areas vm.max_map_count [65530] is too low, increase to
at least [262144]``, then do this:

..  literalinclude:: semehr_fix_vm_settings.sh
    :language: bash


Elasticsearch "high disk watermark..."
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Not clear whether ``high disk watermark exceeded on one or more nodes``
messages from Elasticsearch are critical; it seems to carry on regardless.

However, sometimes we get ``unavailable_shards_exception`` errors from
Elasticsearch, and ``ConnectionTimeout`` errors from SemEHR.

Then, do:
https://stackoverflow.com/questions/30289024/high-disk-watermark-exceeded-even-when-there-is-not-much-data-in-my-index:

..  literalinclude:: semehr_fix_watermark.sh
    :language: bash


Elasticsearch complains about log files (but actually machine learning)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Elasticsearch containers fail to start with an error like ``... Caused by:
java.io.FileNotFoundException:
/tmp/elasticsearch-12074371925419480839/controller_log_1 (No such file or
directory)...``:

- https://github.com/elastic/elasticsearch/issues/43321 -- closed as "user
  issue" but suggests following minimum steps to reproduce:

  .. code-block:: bash

    docker pull docker.elastic.co/elasticsearch/elasticsearch:7.1.1
    docker run -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" docker.elastic.co/elasticsearch/elasticsearch:7.1.1

  Same error on one of my machines, but not another. Both are using Docker
  18.09.7. Note that the earlier part of the error message was: ``"stacktrace":
  ["org.elasticsearch.bootstrap.StartupException: ElasticsearchException[Failed
  to create native process factories for Machine Learning]; nested:
  FileNotFoundException[/tmp/elasticsearch-13081531845067409927/controller_log_1
  (No such file or directory)];",``

- So this may actually relate to machine learning libraries, not logs. Thus:

- https://discuss.elastic.co/t/unable-to-start-elasticsearch-5-4-0-in-docker/84800

- Update Ubuntu on the failing machine (including the kernel, which is the
  relevant bit -- to 4.15.0-66-generic from 4.15.0-62-generic; the "good"
  machine is running 4.15.0-58-generic). Didn't help.

Add this to Docker Compose file:

.. code-block:: yaml

    services:
      es01:
        environment:
          - xpack.security.enabled=false
          - xpack.monitoring.enabled=false
          - xpack.ml.enabled=false
          - xpack.graph.enabled=false
          - xpack.watcher.enabled=false
      es02:
        environment:
          - xpack.security.enabled=false
          - xpack.monitoring.enabled=false
          - xpack.ml.enabled=false
          - xpack.graph.enabled=false
          - xpack.watcher.enabled=false

**Yes**, that fixed it.

- See
  https://www.elastic.co/guide/en/elasticsearch/reference/master/ml-settings.html.
  Machine learning needs a CPU with SSE 4.2. The happy machine has an Intel
  Core i7-3770K and the sad machine has an AMD Phenom II X4 965. Try ``grep
  sse4 /proc/cpuinfo``; the happy machine includes ``sse4_2`` and the sad
  machine doesn't.

- Talk about cryptic error messages...


SemEHR not passing files to Elasticsearch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

I had this from SemEHR:

.. code-block:: none

    total 2 docs to process...
    semehr_processor(569) root 2019-11-07 23:36:33,250 INFO logging to /data/semehr.log
    semehr_processor(574) root 2019-11-07 23:36:33,250 INFO [SemEHR-step] using job status file /data/semehr_job_status_doc_semehr.json
    semehr_processor(580) root 2019-11-07 23:36:33,251 INFO [SemEHR-step]load documents to elasticsearch...
    base(136) elasticsearch 2019-11-07 23:36:43,254 WARNING POST http://172.17.0.1:8200/eprdoc/docs/discharge_summary_14.txt?timeout=30s [status:N/A request:10.002s]
    Traceback (most recent call last):
      File "/usr/local/lib/python2.7/dist-packages/elasticsearch/connection/http_urllib3.py", line 220, in perform_request
        method, url, body, retries=Retry(False), headers=request_headers, **kw
      File "/usr/local/lib/python2.7/dist-packages/urllib3/connectionpool.py", line 641, in urlopen
        _stacktrace=sys.exc_info()[2])
      File "/usr/local/lib/python2.7/dist-packages/urllib3/util/retry.py", line 344, in increment
        raise six.reraise(type(error), error, _stacktrace)
      File "/usr/local/lib/python2.7/dist-packages/urllib3/connectionpool.py", line 603, in urlopen
        chunked=chunked)
      File "/usr/local/lib/python2.7/dist-packages/urllib3/connectionpool.py", line 355, in _make_request
        conn.request(method, url, **httplib_request_kw)
      File "/usr/lib/python2.7/httplib.py", line 1042, in request
        self._send_request(method, url, body, headers)
      File "/usr/lib/python2.7/httplib.py", line 1082, in _send_request
        self.endheaders(body)
      File "/usr/lib/python2.7/httplib.py", line 1038, in endheaders
        self._send_output(message_body)
      File "/usr/lib/python2.7/httplib.py", line 882, in _send_output
        self.send(msg)
      File "/usr/lib/python2.7/httplib.py", line 844, in send
        self.connect()
      File "/usr/local/lib/python2.7/dist-packages/urllib3/connection.py", line 183, in connect
        conn = self._new_conn()
      File "/usr/local/lib/python2.7/dist-packages/urllib3/connection.py", line 165, in _new_conn
        (self.host, self.timeout))
    ConnectTimeoutError: (<urllib3.connection.HTTPConnection object at 0x7fce6f9fce90>, u'Connection to 172.17.0.1 timed out. (connect timeout=10)')

- 172.17.0.1 is a private IP address, and it's the address of the
  Elasticsearch engine.

- Browsing to http://172.17.0.1:8200/ gives a happy Elasticsearch JSON
  answer:

  .. code-block:: none

    {
      "name" : "es01",
      "cluster_name" : "docker-cluster",
      "cluster_uuid" : "GRzBT27MQ3Shni3eK0DVIQ",
      "version" : {
        "number" : "7.1.1",
        "build_flavor" : "default",
        "build_type" : "docker",
        "build_hash" : "7a013de",
        "build_date" : "2019-05-23T14:04:00.380842Z",
        "build_snapshot" : false,
        "lucene_version" : "8.0.0",
        "minimum_wire_compatibility_version" : "6.8.0",
        "minimum_index_compatibility_version" : "6.0.0-beta1"
      },
      "tagline" : "You Know, for Search"
    }

- Browsing to http://172.17.0.1:8200/eprdoc gives:

  .. code-block:: none

    {"error":{"root_cause":[{"type":"index_not_found_exception","reason":"no such index [eprdoc]","index_uuid":"_na_","resource.type":"index_or_alias","resource.id":"eprdoc","index":"eprdoc"}],"type":"index_not_found_exception","reason":"no such index [eprdoc]","index_uuid":"_na_","resource.type":"index_or_alias","resource.id":"eprdoc","index":"eprdoc"},"status":404}

- So, as per
  https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-create-index.html:

  .. code-block:: bash

    curl -X PUT http://172.17.0.1:8200/eprdoc

  ... which should cause a message like ``[index [eprdoc] created]`` on the
  Elasticsearch container console.

- Now, browsing to http://172.17.0.1:8200/eprdoc gives a happier answer:

  .. code-block:: none

    {"eprdoc":{"aliases":{},"mappings":{},"settings":{"index":{"creation_date":"1573169647882","number_of_shards":"1","number_of_replicas":"1","uuid":"yuzy7rNuTauk9thSPXaB6g","version":{"created":"7010199"},"provided_name":"eprdoc"}}}}

- But re-running SemEHR still gives:

  .. code-block:: none

    ConnectTimeoutError: (<urllib3.connection.HTTPConnection object at 0x7fce6f9fced0>, u'Connection to 172.17.0.1 timed out. (connect timeout=10)')
    base(136) elasticsearch 2019-11-07 23:37:07,280 WARNING POST http://172.17.0.1:8200/eprdoc/docs/discharge_summary_14.txt?timeout=30s [status:N/A request:10.010s]

- So, we mimic the call exactly:

  .. code-block:: bash

    curl -v -X POST http://172.17.0.1:8200/eprdoc/docs/discharge_summary_14.txt?timeout=30s
    # ... nope, needs a request body

- The ``semehr-tutorial-run-compose.yml`` file maps the Git root directory
  (``.../CogStack-SemEHR``) to its ``/opt/semehr/CogStack-SemEHR`` directory.
  Within that is ``semehr_processor.py``.

  Working through the Python stack trace, we get to the relevant call from
  ``CogStack-SemEHR/semehr_processor.py`` to
  ``CogStack-SemEHR/analysis/semquery.py``, but then it calls into a Python
  Elasticsearch library that is not in the Git repository, such as
  ``elasticsearch/connection/http_urllib3.py``. However, this file can be found
  within ``/var/lib/docker``.

  So, hack ``http_urllib3.py`` to add these lines (NB Python 2.7):

  .. code-block:: python

    import sys

    # ...

    # In the "try" block of "def perform_request(...)":
    print >>sys.stderr, "URL: %s" % repr(full_url)
    print >>sys.stderr, "Headers: %s" % repr(request_headers)
    print >>sys.stderr, "Body: %s" % repr(body)

  Then rerun the SemEHR container. We see (edited):

  .. code-block:: none

    Headers: {'connection': 'keep-alive', 'content-type': 'application/json'}
    Body: '{"fulltext":"Description: ...","id":"discharge_summary_03.txt","patient_id":"P003"}'

  We can save that data (with Python ``repr`` syntax removed, then edited) as
  ``data.txt``:

  .. code-block:: none

    {
        "fulltext":"Description: Ankylosing spondylitis.",
        "id":"discharge_summary_03.txt",
        "patient_id":"P003"
    }

  and then our ``curl`` command is:

  .. code-block:: bash

    DATAFILE=data.txt
    URL=http://172.17.0.1:8200/eprdoc/docs/discharge_summary_14.txt?timeout=30s
    # Or, for later:
    # URL=http://es01:9200/eprdoc/docs/discharge_summary_14.txt?timeout=30s
    curl -v -X POST  -d @"${DATAFILE}" "${URL}" -H 'connection: keep-alive' -H 'content-type: application/json'

  When it works, we see:

  .. code-block:: none

    'connection: keep-alive' -H 'content-type: application/json'
    Note: Unnecessary use of -X or --request, POST is already inferred.
    *   Trying 172.17.0.1...
    * TCP_NODELAY set
    * Connected to 172.17.0.1 (172.17.0.1) port 8200 (#0)
    > POST /eprdoc/docs/discharge_summary_14.txt?timeout=30s HTTP/1.1
    > Host: 172.17.0.1:8200
    > User-Agent: curl/7.58.0
    > Accept: */*
    > connection: keep-alive
    > content-type: application/json
    > Content-Length: 115
    >
    * upload completely sent off: 115 out of 115 bytes
    < HTTP/1.1 201 Created
    < Location: /eprdoc/docs/discharge_summary_14.txt
    < Warning: 299 Elasticsearch-7.1.1-7a013de "[types removal] Specifying types in document index requests is deprecated, use the typeless endpoints instead (/{index}/_doc/{id}, /{index}/_doc, or /{index}/_create/{id})."
    < content-type: application/json; charset=UTF-8
    < content-length: 177
    <
    * Connection #0 to host 172.17.0.1 left intact
    {"_index":"eprdoc","_type":"docs","_id":"discharge_summary_14.txt","_version":1,"result":"created","_shards":{"total":2,"successful":1,"failed":0},"_seq_no":0,"_primary_term":1}

  But sometimes we see (edited):

  .. code-block:: none

    Note: Unnecessary use of -X or --request, POST is already inferred.
    *   Trying 172.17.0.1...
    * TCP_NODELAY set
    * Connected to 172.17.0.1 (172.17.0.1) port 8200 (#0)
    > POST /eprdoc/docs/discharge_summary_14.txt?timeout=30s HTTP/1.1
    > Host: 172.17.0.1:8200
    > User-Agent: curl/7.58.0
    > Accept: */*
    > connection: keep-alive
    > content-type: application/json
    > Content-Length: 1456
    > Expect: 100-continue
    >
    < HTTP/1.1 100 Continue
    * We are completely uploaded and fine
    < HTTP/1.1 503 Service Unavailable
    < Warning: 299 Elasticsearch-7.1.1-7a013de "[types removal] Specifying types in document index requests is deprecated, use the typeless endpoints instead (/{index}/_doc/{id}, /{index}/_doc, or /{index}/_create/{id})."
    < content-type: application/json; charset=UTF-8
    < content-length: 3415
    <
    {"error":{"root_cause":[{"type":"unavailable_shards_exception","reason":"[eprdoc][0] primary shard is not active Timeout: [30s], request: [BulkShardRequest [[eprdoc][0]] containing [index {[eprdoc][docs][discharge_summary_14.txt], source[{    \"fulltext\":\"Description: <...>* Connection #0 to host 172.17.0.1 left intact
    <...>\",    \"id\":\"discharge_summary_03.txt\",    \"patient_id\":\"P003\"}]}]]"},"status":503}

  and the Elasticsearch console says (excerpt):

  .. code-block:: none

    es01    | {"type": "server", "timestamp": "2019-11-11T10:40:07,723+0000", "level": "WARN", "component": "o.e.c.r.a.DiskThresholdMonitor", "cluster.name": "docker-cluster", "node.name": "es01", "cluster.uuid": "CVehM86XReSKmJsl9PrPhA", "node.id": "iya2H5K6SPS-EO9Co8NhLQ",  "message": "high disk watermark [90%] exceeded on [id7zHXTrQK6kPDJCzJ5eng][es02][/usr/share/elasticsearch/data/nodes/0] free: 68.2gb[9.5%], shards will be relocated away from this node"  }
    es01    | {"type": "server", "timestamp": "2019-11-11T10:40:07,723+0000", "level": "INFO", "component": "o.e.c.r.a.DiskThresholdMonitor", "cluster.name": "docker-cluster", "node.name": "es01", "cluster.uuid": "CVehM86XReSKmJsl9PrPhA", "node.id": "iya2H5K6SPS-EO9Co8NhLQ",  "message": "rerouting shards: [high disk watermark exceeded on one or more nodes]"  }
    es01    | {"type": "server", "timestamp": "2019-11-11T10:40:17,275+0000", "level": "WARN", "component": "r.suppressed", "cluster.name": "docker-cluster", "node.name": "es01", "cluster.uuid": "CVehM86XReSKmJsl9PrPhA", "node.id": "iya2H5K6SPS-EO9Co8NhLQ",  "message": "path: /eprdoc/docs/discharge_summary_14.txt, params: {index=eprdoc, id=discharge_summary_14.txt, type=docs, timeout=30s}" ,
    es01    | "stacktrace": ["org.elasticsearch.action.UnavailableShardsException: [eprdoc][0] primary shard is not active Timeout: [30s], request: [BulkShardRequest [[eprdoc][0]] containing [index {[eprdoc][docs][discharge_summary_14.txt], source[{    \"fulltext\":\"Description: <...>\",    \"id\":\"discharge_summary_03.txt\",    \"patient_id\":\"P003\"}]}]]",
    es01    | "at org.elasticsearch.action.support.replication.TransportReplicationAction$ReroutePhase.retryBecauseUnavailable(TransportReplicationAction.java:968) [elasticsearch-7.1.1.jar:7.1.1]",
    es01    | "at org.elasticsearch.action.support.replication.TransportReplicationAction$ReroutePhase.retryIfUnavailable(TransportReplicationAction.java:845) [elasticsearch-7.1.1.jar:7.1.1]",
    es01    | "at org.elasticsearch.action.support.replication.TransportReplicationAction$ReroutePhase.doRun(TransportReplicationAction.java:797) [elasticsearch-7.1.1.jar:7.1.1]",
    es01    | "at org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:37) [elasticsearch-7.1.1.jar:7.1.1]",
    es01    | "at org.elasticsearch.action.support.replication.TransportReplicationAction$ReroutePhase$2.onTimeout(TransportReplicationAction.java:928) [elasticsearch-7.1.1.jar:7.1.1]",
    es01    | "at org.elasticsearch.cluster.ClusterStateObserver$ContextPreservingListener.onTimeout(ClusterStateObserver.java:322) [elasticsearch-7.1.1.jar:7.1.1]",
    es01    | "at org.elasticsearch.cluster.ClusterStateObserver$ObserverClusterStateListener.onTimeout(ClusterStateObserver.java:249) [elasticsearch-7.1.1.jar:7.1.1]",
    es01    | "at org.elasticsearch.cluster.service.ClusterApplierService$NotifyTimeout.run(ClusterApplierService.java:555) [elasticsearch-7.1.1.jar:7.1.1]",
    es01    | "at org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingRunnable.run(ThreadContext.java:681) [elasticsearch-7.1.1.jar:7.1.1]",
    es01    | "at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1128) [?:?]",
    es01    | "at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:628) [?:?]",
    es01    | "at java.lang.Thread.run(Thread.java:835) [?:?]"] }

- Is the "high disk watermark" thing a problem?

  Fix as above.

  Nope. Makes those "high disk watermark" errors go away, but doesn't stop
  SemEHR failing.

- Make ES be verbose:

  .. code-block:: bash

    # Elasticsearch debug-level logs
    curl -X PUT "localhost:8200/_cluster/settings" -H 'Content-Type: application/json' -d'
        {"transient":{"logger._root":"DEBUG"}}
    '

  ... not especially helpful.

- Make ES log requests:

  https://stackoverflow.com/questions/13821061/log-elasticsearch-requests

  .. code-block:: bash

    # Enable Elasticsearch slow log for "eprdoc" index:
    curl -X "PUT" "http://localhost:8200/eprdoc/_settings?preserve_existing=true" \
         -H 'Content-Type: application/json; charset=utf-8' \
         -d $'{
      "index": {
        "search.slowlog.threshold.query.trace": "0ms",
        "search.slowlog.threshold.fetch.trace": "0ms",
        "search.slowlog.level": "trace"
      }
    }'

Then a more successful line of enquiry:

- Wireshark:

  .. code-block:: bash

    wireshark &

    # Use this display filter:
    http && ip.host matches "^172\."

  Looks like no HTTP traffic is coming from the SemEHR container.

- Shell within a Docker container:

  .. code-block:: bash

    docker run -t -i ianneub/network-tools /bin/bash
    curl http://172.17.0.1:8200/  # aha! Not working.
    exit

    docker run -t -i bytesizedalex/nmap 172.17.0.1
    # ... only port 22.

    nmap 172.17.0.1
    # ...  ports 22, 8080, 8200

    sudo iptables -t nat -S
    # ... is that because the port mapping is via iptables in the host machine?

    docker run -t -i bytesizedalex/nmap 172.21.0.1
    # ... only port 22.

    # ... that Docker nmap command for .2, .3, and .4 all fail.

- OK. Fundamental problem in communicating between Docker containers?

  https://docs.docker.com/v17.09/engine/userguide/networking/default_network/container-communication/#communication-between-containers

  .. code-block:: bash

    sudo iptables -L -n | grep FORWARD
    # ... gives:
    # Chain FORWARD (policy DROP)

    sudo pico /etc/init.d/docker
    # edit from
    #   DOCKER_OPTS=
    # to
    #   DOCKER_OPTS=--icc=true

    sudo service docker restart

    sudo iptables -L -n | grep FORWARD
    # no difference!
    # Reverted.

- As per this:

  https://forums.docker.com/t/communicate-between-two-containers/38646

  "Containers on the same network can use the other[']s container name to
  communicate with each other."

  So let's try:

  .. code-block:: bash

    docker network create semehrnet
    docker network connect semehrnet es01
    docker network connect semehrnet es02
    docker network connect semehrnet tutorial1composefiles_web_1

- Then in ``semehr_settings.json``, do not use ``http://es01:8200/`, but
  use ``http://es01:9200/``.

Success! Edits made to config file to create ``semehrnet`` as above.
