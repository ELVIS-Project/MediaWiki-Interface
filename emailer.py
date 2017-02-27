import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class Emailer:
    def __init__(self, smtp_info, outgoing_addr, outgoing_pass):
        """Sends emails easily.

        Args:
            smtp_info: A tuple with SMTP host and port.
            outgoing_addr: Outgoing email address.
            outgoing_pass: Outgoing email password.
        """
        self._server = None
        self._smtp_info = smtp_info
        self._addr = outgoing_addr
        self._pass = outgoing_pass
        self._last_status_email = datetime.datetime.now()

    def send(self, to, subject, body):
        """Send a message.

        Args:
            to: Recipient email address.
            subject: String of subject.
            body: Body of the email.
        """
        # Create the email.
        msg = MIMEMultipart()
        msg['From'] = self._addr
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # send message
        self._connect()
        self._server.starttls()
        self._server.login(self._addr, self._pass)
        self._server.sendmail(self._addr, to, msg.as_string())
        self._disconnect()

    def _connect(self):
        self._server = smtplib.SMTP(*self._smtp_info)

    def _disconnect(self):
        self._server.quit()
        self._server = None
