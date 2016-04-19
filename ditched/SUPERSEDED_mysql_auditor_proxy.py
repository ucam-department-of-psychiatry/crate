#!/usr/bin/python2.7
# -*- encoding: utf8 -*-

"""
Author: Rudolf Cardinal
Created at: 23 June 2015
Last update: 23 June 2015

Copyright/licensing:

    Copyright (C) 2015-2016 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

===============================================================================
Purpose
===============================================================================
To sit between MySQL clients and a MySQL server and capture queries for audit.

===============================================================================
Other notes
===============================================================================

  * Core proxy method adapted from:
        http://www.mostthingsweb.com/2013/08/a-basic-man-in-the-middle-proxy-with-twisted/  # noqa

  * Testing:
        echo "hello" | nc localhost 3307
        telnet localhost 3307
        mysql --host=127.0.0.1 --port=3307 --user=root --password

  * NOT YET SUPPORTED:
        compression?
        SSL?

  * I'm not the only one to have had this idea - subsequently found this:
        https://vividcortex.com/blog/2014/02/25/performance-schema-slow-query-log-tcp-sniffing/  # noqa
    ... but that is via packet sniffing, not proxies.
    They make the good point that if the proxy is down, that breaks everything.
    Packet sniffing with Twisted:
        http://dound.com/2009/09/integrating-twisted-with-a-pcap-based-python-packet-sniffer/  # noqa
    However, I'm not convinced that packet sniffing is preferable. For a start,
    our use case is to audit and record queries, and so if the auditor is down,
    we *do* want the system to break. Secondly, there is presumably a
    considerable overhead of monitoring all traffic with a packet sniffer and
    filtering that for MySQL. Thirdly, we want this to be able to be specific
    to a MySQL instance. Fourthly, I'm not sure how packet sniffers keep track
    (reliably) of connection state (open/closed, etc.) and they would need to
    be absolutely clear they were following a single thread of conversation,
    since username information only comes through occasionally and we want
    username information to be associated with all audit entries.

  * Then it turns out that MySQL themselves have had this idea:
        http://dev.mysql.com/doc/mysql-proxy/en/
    Theirs does quite a bit, including a daemon mode. The downside seems to be
    that their configurable element is a Lua script. Can also be used for
    sophisticated things like load balancing.
    Easy to install:
        sudo apt-get install mysql-proxy
    The demo scripts live in /usr/share/mysql-proxy, such as auditing.lua
    Can't find anything else, so (after some brief installation) used
        apt-file list mysql-proxy
    ... and it's /usr/bin/mysql-proxy

    Example usage:

        mysql-proxy \
            --log-level=debug \
            --plugins=proxy \
            --proxy-backend-addresses=127.0.0.1:3306 \
            --proxy-address=:4040 \
            --proxy-lua-script=/usr/share/mysql-proxy/auditing.lua

    Well, works in a way, but when you try to log in you get a "bad handshake"
    message. This is with mysql-proxy 0.8.1 and MySQL 5.6.19.

    So,
    - download 0.8.5
    tar xzvf mysql-proxy-0.8.5-linux-glibc2.3-x86-64bit.tar.gz
    cd mysql-proxy-0.8.5-linux-glibc2.3-x86-64bit/bin

    export MYSQLPROXYROOT=~/Downloads/mysql-proxy-0.8.5-linux-glibc2.3-x86-64bit  # noqa
    export MYSQLPROXYDIR=$MYSQLPROXYROOT/bin
    # export MYSQLPROXYSCRIPTDIR=$MYSQLPROXYDIR/share/doc/mysql-proxy
    export MYSQLPROXYSCRIPTDIR=~/Documents/code/anonymise

    $MYSQLPROXYDIR/mysql-proxy \
        --log-level=debug \
        --plugins=proxy \
        --proxy-backend-addresses=127.0.0.1:3306 \
        --proxy-address=:4040 \
        --proxy-lua-script=$MYSQLPROXYSCRIPTDIR/auditing.lua

    $MYSQLPROXYDIR/mysql-proxy \
        --log-level=debug \
        --plugins=proxy \
        --proxy-backend-addresses=127.0.0.1:3306 \
        --proxy-address=:4040 \
        --proxy-lua-script=$MYSQLPROXYSCRIPTDIR/mysql_auditing.lua

    mysql --host=127.0.0.1 --port=4040 --user=root --password

    Now, as the tool is poorly documented with respect to what Lua objects are
    available:

        git clone https://github.com/cwarden/mysql-proxy
        cd mysql-proxy/src
        find . -iname "*.c" -exec grep lua_push {} \;

    Anyway, onwards. Let's create a Lua file.
    - Source IP address extracted.
    - User extracted.
    - Queries extracted.
    - Schema extracted (more reliably than the method used by this script, so
      that alone is a major improvement).

    The downside is that writing the audit log to a database is harder:
        - it'd need a Lua database access system;
        - ... which, if it broke, would mess up everything;
        - it'd likely slow things down considerably, for the situation where
          queries may well be generated programmatically (as I do in R) and
          in large numbers.

    A text log is probably the best way to go here.

"""

from __future__ import print_function
import argparse
# import binascii
from operator import itemgetter
import logging
from twisted.internet import protocol, reactor
from twisted.python import log as twisted_log

LOG_FORMAT = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'
logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT)
log = logging.getLogger("mysql_auditor_proxy")
log.setLevel(logging.DEBUG)

observer = twisted_log.PythonLoggingObserver(loggerName="twisted")
observer.start()


# =============================================================================
# AttrDict
# =============================================================================

class AttrDict(dict):
    # http://stackoverflow.com/questions/4984647
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


# =============================================================================
# MySQL protocol (S = MySQL server, C = client)
# =============================================================================
# https://dev.mysql.com/doc/internals/en/initial-handshake.html
# 1. S->C: Initial_Handshake_Packet
# 2. C->S: either (a) SSL request packet, or (b) handshake response packet, of
#    an old or a new kind.
# We'll assume the first packet is a Protocol::HandshakeResponse packet. See:
#   https://dev.mysql.com/doc/internals/en/connection-phase-packets.html

MYSQL_CAPABILITY_FLAGS = AttrDict(
    # https://dev.mysql.com/doc/internals/en/capability-flags.html
    CLIENT_LONG_PASSWORD=0x00000001,
    CLIENT_FOUND_ROWS=0x00000002,
    CLIENT_LONG_FLAG=0x00000004,
    CLIENT_CONNECT_WITH_DB=0x00000008,
    CLIENT_NO_SCHEMA=0x00000010,
    CLIENT_COMPRESS=0x00000020,
    CLIENT_ODBC=0x00000040,
    CLIENT_LOCAL_FILES=0x00000080,
    CLIENT_IGNORE_SPACE=0x00000100,
    CLIENT_PROTOCOL_41=0x00000200,
    CLIENT_INTERACTIVE=0x00000400,
    CLIENT_SSL=0x00000800,
    CLIENT_IGNORE_SIGPIPE=0x00001000,
    CLIENT_TRANSACTIONS=0x00002000,
    CLIENT_RESERVED=0x00004000,
    CLIENT_SECURE_CONNECTION=0x00008000,
    CLIENT_MULTI_STATEMENTS=0x00010000,
    CLIENT_MULTI_RESULTS=0x00020000,
    CLIENT_PS_MULTI_RESULTS=0x00040000,
    CLIENT_PLUGIN_AUTH=0x00080000,
    CLIENT_CONNECT_ATTRS=0x00100000,
    CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA=0x00200000,
    CLIENT_CAN_HANDLE_EXPIRED_PASSWORDS=0x00400000,
    CLIENT_SESSION_TRACK=0x00800000,
    CLIENT_DEPRECATE_EOF=0x01000000,
)
MYSQL_COMMANDS = AttrDict(
    # https://dev.mysql.com/doc/internals/en/command-phase.html
    COM_INIT_DB=0x02,  # change schema (database)
    COM_QUERY=0x03,  # execute query
    COM_CHANGE_USER=0x11,
    # ... others ignored
)


# noinspection PyUnusedLocal
def map_bitflags(value, flagdict, bits=32, indent=0):
    invdictlist = [(v, k) for k, v in flagdict.items()]
    invdictlist = sorted(invdictlist, key=itemgetter(0))
    s = ""
    for flag, name in invdictlist:
        s += ' ' * indent
        s += "{}: {} (0x{:x})".format(1 if value & flag else 0, name, flag)
        s += '\n'
    return s


def get_integer(index, bytestring, n):
    # https://dev.mysql.com/doc/internals/en/integer.html
    # LSB first = little-endian
    value = 0
    shift = 0
    for i in range(index, index + n):
        b = ord(bytestring[i])
        value += b << shift
        shift += 8
    return index + n, value


def get_fixed_length_string(index, bytestring, n):
    return index + n, bytestring[index:index + n]


def get_null_terminated_string(index, bytestring):
    s = bytestring[index:].split(b'\0', 1)[0]
    return index + len(s) + 1, s


def get_rest_of_packet_string(index, bytestring):
    return len(bytestring), bytestring[index:]


def mysql_packet(data):
    index = 0
    index, payload_length = get_integer(index, data, 3)
    index, sequence_id = get_integer(index, data, 1)
    index, data = get_fixed_length_string(index, data, payload_length)
    return sequence_id, data


# =============================================================================
# Network comms
# =============================================================================

class UserFacing(protocol.Protocol):
    def __init__(self, factory):
        self.factory = factory
        self.buffer = None
        self.mysqlfacing = None
        self.had_packet = False
        # Now the meat:
        self.username = None
        self.schema = None

    def connectionMade(self):
        log.info("UserFacing: connection made")
        factory = MysqlFacingFactory(self)
        reactor.connectTCP(self.factory.serveraddr,
                           self.factory.serverport,
                           factory)

    # client -> this (... -> server)
    def dataReceived(self, data):
        # Inspect and fiddle
        # log.debug("FROM USER: " + data)
        if not self.had_packet:
            self.handshake_packet(data)
            self.had_packet = True
        else:
            self.generic_packet(data)

        # Transmit onwards
        if self.mysqlfacing:
            self.mysqlfacing.write(data)
        else:
            self.buffer = data

    # this -> client
    def write(self, data):
        self.transport.write(data)

    def handshake_packet(self, data):
        log.info("First client -> server packet received")
        # log.debug("Contents: " + binascii.hexlify(data))
        sequence_id, data = mysql_packet(data)
        index = 0
        index, capability_flags = get_integer(index, data, 4)
        index, max_packet_size = get_integer(index, data, 4)
        index, character_set = get_integer(index, data, 1)
        # ... https://dev.mysql.com/doc/internals/en/character-set.html
        index += 23  # then 23 bytes of zero
        index, username = get_null_terminated_string(index, data)
        flagmap = map_bitflags(capability_flags, MYSQL_CAPABILITY_FLAGS,
                               indent=4)
        log.info("Capability flags 0b{:b}\n{}".format(capability_flags,
                                                      flagmap))
        if not capability_flags & MYSQL_CAPABILITY_FLAGS.CLIENT_PROTOCOL_41:
            log.error("Unknown MySQL protocol packet")
        log.info(
            "Max packet size {}; character_set {}; username {}".format(
                max_packet_size,
                character_set,
                username
            )
        )
        self.username = username

    def generic_packet(self, data):
        sequence_id, data = mysql_packet(data)
        index = 0
        index, command = get_integer(index, data, 1)
        if command == MYSQL_COMMANDS.COM_QUERY:
            index, query = get_rest_of_packet_string(index, data)
            self.audit_query(query)
        elif command == MYSQL_COMMANDS.COM_INIT_DB:
            index, schema = get_rest_of_packet_string(index, data)
            self.schema = schema
            log.info("Schema changed to: {}".format(schema))
        elif command == MYSQL_COMMANDS.COM_CHANGE_USER:
            index, username = get_null_terminated_string(index, data)
            self.username = username
            log.info("User changed to: {}".format(username))

    def audit_query(self, query):
        log.info("USER {}, SCHEMA {}, QUERY: {}".format(
            self.username, self.schema, query))


class UserFacingFactory(protocol.ServerFactory):
    def __init__(self, serveraddr, serverport):
        self.serveraddr = serveraddr
        self.serverport = serverport

    def buildProtocol(self, addr):
        return UserFacing(self)


class MysqlFacing(protocol.Protocol):
    def __init__(self, factory):
        self.factory = factory

    def connectionMade(self):
        log.info("MysqlFacing: connection made")
        self.factory.userfacing.mysqlfacing = self
        self.write(self.factory.userfacing.buffer)
        self.factory.userfacing.buffer = ''

    # server -> this (... -> client)
    def dataReceived(self, data):
        # log.debug("FROM SERVER: " + data)
        self.factory.userfacing.write(data)

    # this -> server
    def write(self, data):
        if data:
            self.transport.write(data)


class MysqlFacingFactory(protocol.ClientFactory):
    def __init__(self, userfacing):
        self.userfacing = userfacing

    def buildProtocol(self, addr):
        return MysqlFacing(self)


# =============================================================================
# Main
# =============================================================================

def main():
    # Arguments
    parser = argparse.ArgumentParser(
        description="MySQL TCP man-in-the-middle auditing tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-s", "--mysqlserver", nargs="?", default="localhost")
    parser.add_argument("-p", "--mysqlport", nargs="?", type=int,
                        default=3306)
    parser.add_argument("-l", "--listenport", nargs="?", type=int,
                        default=3307)
    args = parser.parse_args()

    # Go
    log.info("Will forward incoming requests on port {} to {}:{}".format(
        args.listenport, args.mysqlserver, args.mysqlport))
    log.info("Starting Twisted.")
    factory = UserFacingFactory(args.mysqlserver, args.mysqlport)
    reactor.listenTCP(args.listenport, factory)
    reactor.run()


if __name__ == '__main__':
    main()
