#!/usr/bin/env python3
# crate_anon/crateweb/core/mail.py

import smtplib
import ssl
from django.core.mail.backends.smtp import EmailBackend
from django.core.mail.utils import DNS_NAME


class SmtpEmailBackendTls1(EmailBackend):
    """
    Overrides EmailBackend to require TLS v1.
    Use this if your existing TLS server gives the error:
        ssl.SSLEOFError: EOF occurred in violation of protocol (_ssl.c:600)
    ... which appears to be a manifestation of changes in Python's
    smtplib library, which relies on its ssl library, which relies on OpenSSL.
    Something here has changed and now some servers that only support TLS
    version 1.0 don't work. In these situations, the following code fails:
    
        import smtplib
        s = smtplib.SMTP(host, port)  # port typically 587
        print(s.help())  # so we know we're communicating
        s.ehlo()  # ditto
        s.starttls()  # fails with ssl.SSLEOFError as above
    
    and this works:
    
        import smtplib
        import ssl
        s = smtplib.SMTP(host, port)
        c = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        s.ehlo()
        s.starttls(context=c)  # works
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.use_tls:
            raise ValueError("This backend is specifically for TLS.")
        # self.use_ssl will be False, by the superclass's checks
        
    def _protocol(self):
        return ssl.PROTOCOL_TLSv1

    def open(self):
        """
        Ensures we have a connection to the email server. Returns whether or
        not a new connection was required (True or False).
        """
        if self.connection:
            # Nothing to do if the connection is already open.
            return False

        connection_params = {'local_hostname': DNS_NAME.get_fqdn()}
        if self.timeout is not None:
            connection_params['timeout'] = self.timeout
        try:
            self.connection = smtplib.SMTP(self.host, self.port,
                                           **connection_params)

            # TLS
            context = ssl.SSLContext(self._protocol())
            if self.ssl_certfile:
                context.load_cert_chain(certfile=self.ssl_certfile,
                                        keyfile=self.ssl_keyfile)
            self.connection.ehlo()
            self.connection.starttls(context=context)
            self.connection.ehlo()
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except smtplib.SMTPException:
            if not self.fail_silently:
                raise
