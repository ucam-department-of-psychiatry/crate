#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Sends e-mails from the command line.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: 2012
Last update: 22 Feb 2015

Copyright/licensing:

    Copyright (C) 2012-2015 Rudolf Cardinal (rudolf@pobox.com).

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

import argparse
import email.encoders
import email.mime.base
import email.mime.text
import email.mime.multipart
import email.header
import email.utils
import logging
logging.basicConfig()
logger = logging.getLogger("send_email")
logger.setLevel(logging.DEBUG)
import os
import re
import smtplib
import sys


# =============================================================================
# Send e-mail
# =============================================================================

def send_email(sender,
               recipient,
               subject,
               body,
               host,
               user,
               password,
               port=None,
               use_tls=True,
               content_type="text/plain",
               attachment_filenames=[],
               attachment_binaries=[],
               attachment_binary_filenames=[],
               charset="utf8"):
    """Sends an e-mail in text/html format using SMTP via TLS."""
    # http://segfault.in/2010/12/sending-gmail-from-python/
    # http://stackoverflow.com/questions/64505
    # http://stackoverflow.com/questions/3362600
    if port is None:
        port = 587 if use_tls else 25
    if content_type == "text/plain":
        msgbody = email.mime.text.MIMEText(body, "plain", charset)
    elif content_type == "text/html":
        msgbody = email.mime.text.MIMEText(body, "html", charset)
    else:
        errmsg = "send_email: unknown content_type"
        logger.error(errmsg)
        return (False, errmsg)

    # Make message
    msg = email.mime.multipart.MIMEMultipart()
    msg["From"] = sender
    if type(recipient) == list:
        msg["To"] = ", ".join(recipient)
    else:
        msg["To"] = recipient
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Subject"] = subject
    msg.attach(msgbody)

    # Attachments
    try:
        if attachment_filenames is not None:
            for f in attachment_filenames:
                part = email.mime.base.MIMEBase("application", "octet-stream")
                part.set_payload(open(f, "rb").read())
                email.encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    'attachment; filename="%s"' % os.path.basename(f)
                )
                msg.attach(part)
        if (attachment_binaries is not None
                and attachment_binary_filenames is not None
                and (
                    len(attachment_binaries) ==
                    len(attachment_binary_filenames)
                )):
            for i in range(len(attachment_binaries)):
                blob = attachment_binaries[i]
                filename = attachment_binary_filenames[i]
                part = email.mime.base.MIMEBase("application", "octet-stream")
                part.set_payload(blob)
                email.encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    'attachment; filename="%s"' % filename)
                msg.attach(part)
    except:
        errmsg = "send_email: Failed to attach files"
        logger.error(errmsg)
        return (False, errmsg)

    # Connect
    try:
        session = smtplib.SMTP(host, port)
    except:
        errmsg = "send_email: Failed to connect to host {}, port {}".format(
            host, port)
        logger.error(errmsg)
        return (False, errmsg)
    try:
        session.ehlo()
        session.starttls()
        session.ehlo()
    except:
        errmsg = "send_email: Failed to initiate TLS"
        logger.error(errmsg)
        return (False, errmsg)

    # Log in
    try:
        session.login(user, password)
    except:
        errmsg = "send_email: Failed to login as user {}".format(user)
        logger.error(errmsg)
        return (False, errmsg)

    # Send
    try:
        session.sendmail(sender, recipient, msg.as_string())
    except Exception as e:
        errmsg = "send_email: Failed to send e-mail: exception: " + str(e)
        logger.error(errmsg)
        return (False, errmsg)

    # Log out
    session.quit()

    return (True, "Success")

# =============================================================================
# Misc
# =============================================================================

_SIMPLE_EMAIL_REGEX = re.compile("[^@]+@[^@]+\.[^@]+")


def is_email_valid(email):
    """Performs a very basic check that a string appears to be an e-mail
    address."""
    # Very basic checks!
    return _SIMPLE_EMAIL_REGEX.match(email)


def get_email_domain(email):
    """Returns the domain part of an e-mail address."""
    return email.split("@")[1]


# =============================================================================
# Parse command line
# =============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Send an e-mail from the command line.")
    parser.add_argument("sender", action="store",
                        help="Sender's e-mail address")
    parser.add_argument("host", action="store",
                        help="SMTP server hostname")
    parser.add_argument("user", action="store",
                        help="SMTP username")
    parser.add_argument("password", action="store",
                        help="SMTP password")
    parser.add_argument("recipient", action="append",
                        help="Recipient e-mail address(es)")
    parser.add_argument("subject", action="store",
                        help="Message subject")
    parser.add_argument("body", action="store",
                        help="Message body")
    parser.add_argument("--attach", action="append",
                        help="Filename(s) to attach")
    parser.add_argument("--tls", action="store_false",
                        help="Use TLS connection security")
    parser.add_argument("-h --help", action="help",
                        help="Prints this help")
    args = parser.parse_args()
    (result, msg) = send_email(
        args.sender,
        args.recipient,
        args.subject,
        args.body,
        args.host,
        args.user,
        args.password,
        use_tls=args.tls,
        attachment_filenames=args.attach
    )
    if result:
        print("Success")
    else:
        print("Failure\n{}".format(msg))
    sys.exit(0 if result else 1)
