#!/usr/bin/python
# -*- encoding: utf8 -*-

"""whisker.py: Support functions for Whisker clients.

http://egret.psychol.cam.ac.uk/pythonlib/whisker.py

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: 18 Aug 2011
Last update: 24 Sep 2015

TO IMPORT REMOTELY:
    http://stackoverflow.com/questions/3799545/dynamically-importing-python-module  # noqa
    http://code.activestate.com/recipes/82234-importing-a-dynamically-generated-module/  # noqa

import imp
import urllib
WHISKER_MODULE_URL = "http://egret.psychol.cam.ac.uk/pythonlib/whisker.py"
WHISKER_MODULE_CODE = urllib.urlopen(WHISKER_MODULE_URL).read()
whisker = imp.new_module("whisker")
exec WHISKER_MODULE_CODE in whisker.__dict__

Copyright/licensing:

    Copyright (C) 2011-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""


# =============================================================================
# Dependencies
# =============================================================================

# Python Standard Library:
from __future__ import division, print_function, absolute_import
import logging
import re
import socket
import time

# Additional:

# Installing Twisted:
#   (1) Ubuntu
#           sudo apt-get install python-twisted
#       If problems:
#           sudo pip install zope.interface==3.6.0
from twisted.internet import reactor  # PYTHON 3: sudo pip3 install twisted
# from twisted.internet.stdio import StandardIO
from twisted.internet.protocol import ClientFactory
from twisted.protocols.basic import LineReceiver


# =============================================================================
# Module-level variables
# =============================================================================

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.DEBUG)

EVENT_PREFIX = "Event: "
KEY_EVENT_PREFIX = "KeyEvent: "
CLIENT_MESSAGE_PREFIX = "ClientMessage: "
INFO_PREFIX = "Info: "
WARNING_PREFIX = "Warning: "
SYNTAX_ERROR_PREFIX = "SyntaxError: "
ERROR_PREFIX = "Error: "


# =============================================================================
# Helper functions
# =============================================================================

def get_port(x):
    if type(x) is int:
        return x
    m = re.match(r"\D", x)  # search for \D = non-digit characters
    if m:
        port = socket.getservbyname(x, "tcp")
    else:
        port = int(x)
    return port


def split_terminal_timestamp(msg):
    try:
        m = re.match("(.*)\s+\[(\w+)\]$", msg)
        mainmsg = m.group(1)
        timestamp = int(m.group(2))
        return (mainmsg, timestamp)
    except:
        return (msg, None)


def on_off_to_boolean(msg):
    return True if msg == "on" else False


# =============================================================================
# Basic Whisker class, in which clients do all the work
# =============================================================================

class Whisker(object):
    """Basic Whisker class, in which clients do all the work.
    (Not sophisticated. Use WhiskerTask instead.)
    Typical usage:

        from __future__ import print_function
        import sys
        import whisker
        w = whisker.Whisker()
        if not w.connect_both_ports(options.server, options.port):
            sys.exit()

        w.send("ReportName Whisker python demo program")
        w.send("WhiskerStatus")
        reply = w.send_immediate("TimerSetEvent 1000 9 TimerFired")
        reply = w.send_immediate("TimerSetEvent 12000 0 EndOfTask")
        w.send("TestNetworkLatency")

        for line in w.getlines_mainsock():
            if options.verbosenetwork:
                print("SERVER: " + line)  # For info only.
            if line == "Ping":
                # If the server has sent us a Ping, acknowledge it.
                w.send("PingAcknowledged")
            if line[:7] == "Event: ":
                # The server has sent us an event.
                event = line[7:]
                if options.verbosenetwork:
                    print("EVENT RECEIVED: " + event)  # For info only.
                # Event handling for the behavioural task is dealt with here.
                if event == "EndOfTask":
                    break  # Exit the while loop.
    """

    BUFFERSIZE = 4096

    def __init__(self):
        self.mainsock = None
        self.immsock = None

    @classmethod
    def set_verbose_logging(cls, verbose):
        if verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

    def connect_both_ports(self, server, mainport):
        """Connect the main and immediate ports to the server."""
        if not self.connect_main(server, mainport):  # Log in to the server.
            return False
        # Listen to the server until we can connect the immediate socket.
        for line in self.getlines_mainsock():
            # The server has sent us a message via the main socket.
            logger.debug("SERVER: " + line)
            m = re.search(r"^ImmPort: (\d+)", line)
            if m:
                immport = m.group(1)
            m = re.search(r"^Code: (\w+)", line)
            if m:
                code = m.group(1)
                if not self.connect_immediate(server, immport, code):
                    return False
                break
        return True

    def connect_main(self, server, portstring):
        """Connect the main port to the server."""
        logger.info("Connecting main port to server.")
        port = get_port(portstring)
        proto = socket.getprotobyname("tcp")
        try:
            self.mainsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM,
                                          proto)
            self.mainsock.connect((server, port))
        except socket.error as x:
            # "except socket.error, msg" used to work; see
            # http://stackoverflow.com/questions/2535760
            self.mainsock.close()
            self.mainsock = None
            logger.error("ERROR creating/connecting main socket: " + str(x))
            return False
        logger.info("Connected to main port " + str(port) +
                    " on server " + server)

        # Disable the Nagle algorithm:
        self.mainsock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        return True

    def connect_immediate(self, server, portstring, code):
        port = get_port(portstring)
        proto = socket.getprotobyname("tcp")
        try:
            self.immsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM,
                                         proto)
            self.immsock.connect((server, port))
        except socket.error as x:
            self.immsock.close()
            self.immsock = None
            logger.error("ERROR creating/connecting immediate socket: " +
                         str(x))
            return False
        logger.info("Connected to immediate port " + str(port) +
                    " on server " + server)

        # Disable the Nagle algorithm:
        self.immsock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        self.immsock.setblocking(True)
        self.send_immediate("Link "+code)
        sleeptime = 0.1
        logger.info("Sleeping for " + str(sleeptime) +
                    " seconds as the Nagle-disabling feature of Python "
                    "isn't working properly...")
        time.sleep(sleeptime)
        # the Nagle business isn't working; the Link packet is getting
        # amalgamated with anything the main calling program starts to send.
        # So pause.
        logger.info("... continuing. Immediate socket should now be "
                    "correctly linked.")
        return True

    def log_out(self):
        try:
            self.mainsock.close()
        except socket.error as x:
            logger.error("Error closing main socket: " + str(x))
        try:
            self.immsock.close()
        except socket.error as x:
            logger.error("Error closing immediate socket: " + str(x))

    def send(self, s):
        """Send something to the server on the main socket, with a trailing
        newline."""
        logger.debug("Main socket command: " + s)
        self.mainsock.send(s + "\n")

    def send_immediate(self, s):
        """Send a command to the server on the immediate socket, and retrieve
        its reply."""
        logger.debug("Immediate socket command: " + s)
        self.immsock.sendall(s + "\n")
        reply = self.getlines_immsock().next()
        logger.debug("Immediate socket reply: " + reply)
        return reply

    def getlines_immsock(self):
        """Yield a set of lines from the socket."""
        # http://stackoverflow.com/questions/822001/python-sockets-buffering
        buf = self.immsock.recv(Whisker.BUFFERSIZE)
        done = False
        while not done:
            if "\n" in buf:
                (line, buf) = buf.split("\n", 1)
                yield line
            else:
                more = self.immsock.recv(Whisker.BUFFERSIZE)
                if not more:
                    done = True
                else:
                    buf = buf + more
        if buf:
            yield buf

    def getlines_mainsock(self):
        """Yield a set of lines from the socket."""
        buf = self.mainsock.recv(Whisker.BUFFERSIZE)
        done = False
        while not done:
            if "\n" in buf:
                (line, buf) = buf.split("\n", 1)
                yield line
            else:
                more = self.mainsock.recv(Whisker.BUFFERSIZE)
                if not more:
                    done = True
                else:
                    buf = buf + more
        if buf:
            yield buf


# =============================================================================
# Event-driven Whisker task class. Use this one.
# =============================================================================

class WhiskerTask(object):
    """Usage: see test_whisker() function."""

    def __init__(self):
        self.server = None
        self.mainport = None
        self.immport = None
        self.code = None
        self.mainsocket = None
        self.immsocket = None
        self.mainfactory = WhiskerMainPortFactory(self)

    @classmethod
    def set_verbose_logging(cls, verbose):
        if verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

    def connect(self, server, port):
        self.server = server
        self.mainport = get_port(port)
        logger.info(
            "Attempting to connect to Whisker server {s} on port {p}".format(
                s=self.server,
                p=self.mainport
            ))
        reactor.connectTCP(self.server, self.mainport, self.mainfactory)

    def connect_immediate(self):
        # Twisted really hates blocking.
        # So we need to do some special things here.
        self.immsocket = WhiskerImmSocket(self)
        logger.info(
            "Attempting to connect to Whisker server {s} on immediate "
            "port {p}".format(
                s=self.server,
                p=self.immport
            ))
        self.immsocket.connect(self.server, self.immport)
        if not self.immsocket.connected:
            logger.error("ERROR creating/connecting immediate socket: " +
                         str(self.immsocket.error))
        logger.info("Connected to immediate port " + str(self.immport) +
                    " on server " + self.server)
        self.immsocket.send_and_get_reply("Link " + self.code)
        logger.info("Server fully connected.")
        self.fully_connected()

        # sleeptime = 0.1
        # logger.info("Sleeping for " + str(sleeptime) +
        #                  " seconds as the Nagle-disabling feature of Python "
        #                  "isn't working properly...")
        # time.sleep(sleeptime)
        # The Nagle business isn't working; the Link packet is getting
        # amalgamated with anything the main calling program starts to send.
        # So pause.

    def fully_connected(self):
        """Override this."""
        pass

    def send(self, msg):
        if not self.mainsocket:
            logger.error("can't send without a mainsocket")
            return
        self.mainsocket.send(msg)

    def send_and_get_reply(self, msg):
        if not self.immsocket:
            logger.error("can't send_and_get_reply without an immsocket")
            return
        reply = self.immsocket.send_and_get_reply(msg)
        return reply

    def command(self, cmd):
        return self.send_and_get_reply(cmd)

    def incoming_message(self, msg):
        logger.debug("INCOMING MESSAGE: " + str(msg))
        handled = False
        if not self.immport:
            m = re.search(r"^ImmPort: (\d+)", msg)
            if m:
                self.immport = get_port(m.group(1))
                handled = True
        if not self.code:
            m = re.search(r"^Code: (\w+)", msg)
            if m:
                self.code = m.group(1)
                handled = True
        if (not self.immsocket) and (self.immport and self.code):
            self.connect_immediate()
        if handled:
            return

        (msg, timestamp) = split_terminal_timestamp(msg)

        if msg == "Ping":
            # If the server has sent us a Ping, acknowledge it.
            self.send("PingAcknowledged")
            return

        if msg.startswith(EVENT_PREFIX):
            # The server has sent us an event.
            event = msg[len(EVENT_PREFIX):]
            self.incoming_event(event, timestamp)
            return

        if msg.startswith(KEY_EVENT_PREFIX):
            kmsg = msg[len(KEY_EVENT_PREFIX):]
            # key on|off document
            m = re.match(r"(\w+)\s+(\w+)\s+(\w+)", kmsg)
            if m:
                key = m.group(1)
                depressed = on_off_to_boolean(m.group(2))
                document = m.group(3)
                self.incoming_key_event(key, depressed, document, timestamp)
            return

        if msg.startswith(CLIENT_MESSAGE_PREFIX):
            cmsg = msg[len(CLIENT_MESSAGE_PREFIX):]
            # fromclientnum message
            m = re.match(r"(\w+)\s+(.+)", cmsg)
            if m:
                try:
                    fromclientnum = int(m.group(1))
                    clientmsg = m.group(2)
                    self.incoming_client_message(fromclientnum, clientmsg,
                                                 timestamp)
                except (TypeError, ValueError):
                    pass
            return

        if msg.startswith(INFO_PREFIX):
            self.incoming_info(msg)
            return

        if msg.startswith(WARNING_PREFIX):
            self.incoming_warning(msg)
            return

        if msg.startswith(SYNTAX_ERROR_PREFIX):
            self.incoming_syntax_error(msg)
            return

        if msg.startswith(ERROR_PREFIX):
            self.incoming_error(msg)
            return

        logger.debug("Unhandled incoming_message: " + str(msg))

    def incoming_event(self, event, timestamp=None):
        """Override this."""
        logger.debug("UNHANDLED EVENT: {e} (timestamp={t}".format(
            e=event,
            t=timestamp
        ))

    def incoming_client_message(self, fromclientnum, msg, timestamp=None):
        """Override this."""
        logger.debug(
            "UNHANDLED CLIENT MESSAGE from client {c}: {m} "
            "(timestamp={t})".format(
                c=fromclientnum,
                m=msg,
                t=timestamp
            ))

    def incoming_key_event(self, key, depressed, document, timestamp=None):
        """Override this."""
        logger.debug(
            "UNHANDLED KEY EVENT: key {k} {dr} (document={d}, "
            "timestamp={t})".format(
                k=key,
                dr="depressed" if depressed else "released",
                d=document,
                t=timestamp
            ))

    def incoming_info(self, msg):
        """Override this."""
        logger.debug(msg)

    def incoming_warning(self, msg):
        """Override this."""
        logger.debug(msg)

    def incoming_error(self, msg):
        """Override this."""
        logger.debug(msg)

    def incoming_syntax_error(self, msg):
        """Override this."""
        logger.debug(msg)


class WhiskerMainPortFactory(ClientFactory):

    def __init__(self, task):
        self.task = task

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        logger.error("connection failed: " + str(reason))
        reactor.stop()

    def buildProtocol(self, addr):
        if self.task.mainsocket:
            logger.error("mainsocket already connected")
            return None
        p = WhiskerMainPortProtocol(self.task)
        return p


class WhiskerMainPortProtocol(LineReceiver):

    delimiter = "\n"

    def __init__(self, task):
        self.task = task
        self.task.mainsocket = self

    def connectionMade(self):
        peer = self.transport.getPeer()
        if hasattr(peer, "host") and hasattr(peer, "port"):
            logger.info("Connected to main port {p} on server {h}".format(
                h=peer.host,
                p=peer.port
            ))
        else:
            logger.debug("Connected to main port")
        self.transport.setTcpNoDelay(True)  # disable Nagle algorithm
        logger.debug("Main port: Nagle algorithm disabled (TCP_NODELAY set)")

    def lineReceived(self, data):
        logger.debug("Main port received: " + str(data))
        self.task.incoming_message(data)

    def send(self, data):
        logger.debug("Main port sending: " + str(data))
        self.sendLine(data)


class WhiskerImmSocket(object):
    """Uses raw sockets."""
    BUFFERSIZE = 4096

    def __init__(self, task):
        self.task = task
        self.connected = False
        self.error = ""
        self.immsock = None

    def connect(self, server, port):
        proto = socket.getprotobyname("tcp")
        try:
            self.immsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM,
                                         proto)
            self.immsock.connect((server, port))
            self.connected = True
        except socket.error as x:
            self.immsock.close()
            self.immsock = None
            self.error = str(x)
            return

        # Disable the Nagle algorithm:
        self.immsock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        logger.debug("Immediate port: Nagle algorithm disabled (TCP_NODELAY "
                     "set)")
        # Set blocking
        self.immsock.setblocking(True)
        logger.debug("Immediate port: set to blocking mode")

    def getlines_immsock(self):
        """Yield a set of lines from the socket."""
        # http://stackoverflow.com/questions/822001/python-sockets-buffering
        buf = self.immsock.recv(WhiskerImmSocket.BUFFERSIZE)
        done = False
        while not done:
            if "\n" in buf:
                (line, buf) = buf.split("\n", 1)
                yield line
            else:
                more = self.immsock.recv(Whisker.BUFFERSIZE)
                if not more:
                    done = True
                else:
                    buf = buf + more
        if buf:
            yield buf

    def send_and_get_reply(self, msg):
        logger.debug("Immediate socket sending: " + msg)
        self.immsock.sendall(msg + "\n")
        reply = self.getlines_immsock().next()
        logger.debug("Immediate socket reply: " + reply)
        return reply


def test_whisker(server="localhost", port=3233):

    class MyWhiskerTask(WhiskerTask):

        def __init__(self, ):
            super(MyWhiskerTask, self).__init__()  # call base class init
            # ... anything extra here

        def fully_connected(self):
            print("SENDING SOME TEST/DEMONSTRATION COMMANDS")
            self.command("Timestamps on")
            self.command("ReportName WHISKER_CLIENT_PROTOTYPE")
            self.send("TestNetworkLatency")
            self.command("TimerSetEvent 1000 9 TimerFired")
            self.command("TimerSetEvent 12000 0 EndOfTask")

        def incoming_event(self, event, timestamp=None):
            print("Event: {e} (timestamp {t})".format(e=event, t=timestamp))
            if event == "EndOfTask":
                reactor.stop()

    w = MyWhiskerTask()
    w.connect(server, port)
    reactor.run()

if __name__ == '__main__':
    print("Module run explicitly. Running a Whisker test.")
    test_whisker()
    # test_whisker("wombatvmxp")
