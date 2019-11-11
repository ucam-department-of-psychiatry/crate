.. crate_anon/docs/source/misc/semehr.rst

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

.. _Docker: https://www.docker.com
.. _Docker Compose: https://docs.docker.com/compose/
.. _Docker Desktop for Windows: https://docs.docker.com/docker-for-windows/install/
.. _Elasticsearch: https://www.elastic.co/products/elasticsearch


Using SemEHR
============

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

.. code-block:: bash

    # -------------------------------------------------------------------------
    # Definitions
    # -------------------------------------------------------------------------
    # We will make this directory:
    TUTORIALDIR=${HOME}/tmp/semehr_tutorial1

    # This should already exist and contain your Bio-YODIE installation:
    BIOYODIEDIR=${HOME}/dev/yodie-pipeline-1-2-umls-only

    # Other directories and files we'll use:
    # - Root directory of SemEHR Git repository
    GITDIR=${TUTORIALDIR}/CogStack-SemEHR
    # - Docker Compose tutorial directory within SemEHR tree
    COMPOSEDIR=${GITDIR}/tutorials/tutorial1_compose_files
    # - Docker Compose file to launch Elasticsearch
    ELASTICSEARCH_COMPOSE=${COMPOSEDIR}/semehr-tutorial1-servers-compose.yml
    # - Docker Compose file to launch SemEHR
    SEMEHR_COMPOSE=${COMPOSEDIR}/semehr-tutorial-run-compose.yml
    # - Data directory
    DATADIR=${GITDIR}/tutorials/mtsamples-cohort
    SEMEHR_CONFIG=${DATADIR}/semehr_settings.json

    # -------------------------------------------------------------------------
    # Setup actions
    # -------------------------------------------------------------------------
    # Make directory
    mkdir -p ${TUTORIALDIR}
    # Copy in UMLS
    cp -R ${BIOYODIEDIR}/bio-yodie-resources ${TUTORIALDIR}
    # Fetch SemEHR code
    git clone https://github.com/CogStack/CogStack-SemEHR.git "${GITDIR}"

    # Copy/edit Docker Compose file (as default name of docker-compose.yml).
    # Point to our files, not some hard-coded root-based path:
    sed -i "s,device: /semehr_tutorial1/,device: ${TUTORIALDIR}/,g" "${ELASTICSEARCH_COMPOSE}"
    sed -i "s,device: /semehr_tutorial1/,device: ${TUTORIALDIR}/,g" "${SEMEHR_COMPOSE}"

    # Bugfix as per Honghan Wu 2019-11-10: fix Docker gateway address
    sed -i "s,http://172.17.0.1,http://172.21.0.1,g" "${SEMEHR_CONFIG}"  # NOT YET RIGHT ***

    sed -i "s,http://172.21.0.1,http://es01,g" "${SEMEHR_CONFIG}"  # NOT YET RIGHT ***
    sed -i "s,http://es01,http://es02,g" "${SEMEHR_CONFIG}"  # NOT YET RIGHT ***
    sed -i "s,http://es02,http://web,g" "${SEMEHR_CONFIG}"  # NOT YET RIGHT ***

    # -------------------------------------------------------------------------
    # Start
    # -------------------------------------------------------------------------
    # Start the containers (will fetch all necessary software the first time).
    # Run in foreground mode, so we can see the log output.
    docker-compose -f "${ELASTICSEARCH_COMPOSE}" up

Once the Elasticsearch containers are happy, you can (if you want) shut them
down (``Ctrl-C``) and restart them in the background:

.. code-block:: bash

    docker-compose -f "${ELASTICSEARCH_COMPOSE}" up -d

    # NOT NOW, but when you want to shut it down:
    docker-compose -f "${ELASTICSEARCH_COMPOSE}" down
    # And if you want to remove the container:
    docker-compose -f "${ELASTICSEARCH_COMPOSE}" rm -f

Alternatively, you could fire up another terminal (and enter the same variable
definitions as above) to see both operating.

Now run SemEHR:

.. code-block:: bash

    docker-compose -f "${SEMEHR_COMPOSE}" run semehr

Browse to http://127.0.0.1:8080/SemEHR.html and try searching for patient
``P001``. Try also http://127.0.0.1:8200/_cat/indices/, which should show
current indices (you expect one called ``eprdoc``).


Docker information and debugging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- You can explore what's going on:

  .. code-block:: bash

    # And to explore what's going on:
    docker-compose -f <COMPOSEFILE> images
    docker-compose -f <COMPOSEFILE> top
    docker images
    docker container ls
    docker stats  # Ctrl-C to finish
    docker ps
    docker network ls
    docker network inspect $(docker network ls -q)

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


Troubleshooting SemEHR
~~~~~~~~~~~~~~~~~~~~~~

- **Factoids about the SemEHR setup.**

  - I think the file that configures SemEHR is
    ``CogStack-SemEHR/tutorials/mtsamples-cohort/semehr_settings.json``. The
    directory ``CogStack-SemEHR/tutorials/mtsamples-cohort`` is mounted by the
    SemEHR Docker Console file as the primary data directory for the container.
    You will find ``semehr.log`` being written to the same directory.

  - The JSON config file format is described at
    https://github.com/CogStack/CogStack-SemEHR/wiki.

    - The Elasticsearch URL (including the IP address of the other Docker
      container) is configured by ``es_host`` and ``es_doc_url``.

- **Persistent wrong Docker paths.**

  If you started a container based on a ``.yml`` file with wrong directories,
  the settings can persist. Try ``docker container ls`` followed by ``docker
  container rm ...``, but if there are no containers listed yet the problem
  still persists, try ``docker image ls`` followed by ``docker image rm
  <IMAGE_ID>``. Then the container will be rebuilt when you next restart it.
  If that doesn't work, try ``docker images purge`` and ``docker system prune
  -a``, delete the tutorial directory, and start again.

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

  - This was on 2019-11-08 after wiping everything I'd thought of. So it seems
    that the thing that is being persisted/cached is the volume.

  - A few calls to ``docker volume rm ...`` later... and it's happy.

  - Lesson: containers and volumes are independent!

  - Still problems, though. Complete purge, as above.

- **Errors relating to a full disk.**

  If you see ``INTERNAL ERROR: cannot create temporary directory!``, your disk
  is probably full. (Lots of rubbish in ``/var/spool/mail/root``, for example?)

- **Elasticsearch complains about vm.max_map_count.**

  If the Elasticsearch containers fail to start and give the error message
  ``max virtual memory areas vm.max_map_count [65530] is too low, increase to
  at least [262144]``, then do this:

  .. code-block:: bash

    sysctl vm.max_map_count  # read
    sudo sysctl -w vm.max_map_count=262144  # write
    sysctl vm.max_map_count  # re-read, should have changed

- **Elasticsearch "high disk watermark..."**

  Don't worry about ``high disk watermark exceeded on one or more nodes``
  messages from Elasticsearch; it seems to carry on regardless.

- **Elasticsearch complains about log files (but actually machine learning).**

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
    18.09.7. Note that the earlier part of the error message was:
    ``"stacktrace": ["org.elasticsearch.bootstrap.StartupException:
    ElasticsearchException[Failed to create native process factories for
    Machine Learning]; nested:
    FileNotFoundException[/tmp/elasticsearch-13081531845067409927/controller_log_1
    (No such file or directory)];",``

  - So this may actually relate to machine learning libraries, not logs. Thus:

  - https://discuss.elastic.co/t/unable-to-start-elasticsearch-5-4-0-in-docker/84800

  - Update Ubuntu on the failing machine (including the kernel, which is the
    relevant bit -- to 4.15.0-66-generic from 4.15.0-62-generic; the "good"
    machine is running 4.15.0-58-generic). Didn't help.

  - Add this to Docker Compose file:

    .. code-block:: yml

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

    **yes**, that fixed it.

  - See
    https://www.elastic.co/guide/en/elasticsearch/reference/master/ml-settings.html.
    Machine learning needs a CPU with SSE 4.2. The happy machine has an Intel
    Core i7-3770K and the sad machine has an AMD Phenom II X4 965. Try ``grep
    sse4 /proc/cpuinfo``; the happy machine includes ``sse4_2`` and the sad
    machine doesn't.

  - Talk about cryptic error messages...

- **SemEHR not passing files to Elasticsearch. ONGOING.**

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

    .. code-block::

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

  **CURRENTLY STUCK.**

Notes
~~~~~

- The ``web`` container has some SemEHR data mapped to its
  ``/usr/local/apache2/htdocs/`` directory, and exposes web services on port
  8080 (external), mapped to its internal port 80.
