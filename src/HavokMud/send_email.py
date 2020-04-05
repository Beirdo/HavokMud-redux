import html
import logging
import re
import stackless
from threading import Lock

import boto3
import requests
from botocore.exceptions import ClientError
from urlextract import URLExtract
from html2text import HTML2Text

logger = logging.getLogger(__name__)


class EmailRequest(object):
    def __init__(self, from_, to, subject, body_html=None, body_text=None):
        self.from_ = from_
        self.to = to
        self.subject = subject
        self.body_html = body_html
        self.body_text = body_text
        self.channel = stackless.channel()


class EmailHandler(object):
    def __init__(self, config):
        self.config = config

        self.region = self.config.get("mud", {}).get("region", "us-east-1")

        email_config = self.config.get("email", {})
        self.endpoint = email_config.get("endpoint", None)
        self.use_ssl = email_config.get("useSsl", True)

        self.session = boto3.session.Session(region_name=self.region)
        self.ses = self.session.client('ses', endpoint_url=self.endpoint, use_ssl=self.use_ssl)

        self.mocked = email_config.get("mocked", False)

        self.extractor = URLExtract()
        self.extractor.update = self._update_tlds
        self.extractor_lock = Lock()

        self.url_re = re.compile(r'^(?P<type>.*://)?(?P<remainder>.*)$')
        self.html2text = HTML2Text()
        self.html2text.ignore_links = False
        self.html2text.ignore_images = False
        self.html2text.ignore_tables = False
        self.html2text.ignore_emphasis = False
        self.html2text_lock = Lock()

        self.in_channel = stackless.channel()

        stackless.tasklet(self._send_email_loop)()

    def _update_tlds(self):
        response = requests.get("https://data.iana.org/TLD/tlds-alpha-by-domain.txt")
        data = response.content
        # noinspection PyProtectedMember
        filename = self.extractor._get_cache_file_path(None)
        with open(filename, "wb") as f:
            f.write(data)
        # noinspection PyProtectedMember
        self.extractor._reload_tlds_from_file()
        return True

    def send_email(self, from_, to, subject, body_html=None, body_text=None):
        request = EmailRequest(from_, to, subject, body_html, body_text)
        self.in_channel.send(request)
        response = request.channel.receive()
        return response

    def _send_email_loop(self):
        while True:
            request = self.in_channel.receive()
            stackless.tasklet(self._send_email_tasklet)(request)

    def _send_email_tasklet(self, request):
        response = {}
        try:
            logger.info("Sending email from %s to %s" % (request.from_, request.to))
            if not request.body_html:
                if not request.body_text:
                    raise Exception("No body given")

                request.body_html = self.htmlize_body(request.body_text)

            if not request.body_text:
                request.body_text = self.unhtmlize_body(request.body_html)

            email = {
                "Destination": {
                    "ToAddresses": [
                        request.to,
                    ],
                },
                "Source": request.from_,
                "Message": {
                    "Body": {
                        "Html": {
                            "Charset": "utf-8",
                            "Data": request.body_html,
                        },
                        "Text": {
                            "Charset": "utf-8",
                            "Data": request.body_text,
                        },
                    },
                    "Subject": {
                        "Charset": "utf-8",
                        "Data": request.subject,
                    },
                },
                "ConfigurationSetName": "havokmud",
            }

            # This is necessary for SES to send the email
            # When using localstack, we "verify" as we go
            # In real life, the domain should be verified before using this, preferrably
            # by using Easy DKIM.
            if self.mocked:
                self.ses.verify_email_identity(EmailAddress=request.from_)

            response = self.ses.send_email(**email)
            logger.info("Email sent: MessageID: %s" % response.get("MessageId", None))
        except ClientError as e:
            # Display an error if something goes wrong.
            logger.error("Error sending email: %s" % e.response.get("Error", {}).get("Message", "unknown error"))
            response = e.response['Error']['Message']
        except Exception as e:
            logger.exception("Error sending email: %s" % str(e))
            response = {"Error": {"Message": str(e)}}

        request.channel.send(response)

    def htmlize_body(self, text):
        # Want to put links on URLs, and make the rest html-safe
        with self.extractor_lock:
            self.extractor.update_when_older(7)

            input = text
            output = b"<html><body>"
            while input:
                urls = self.extractor.find_urls(input)
                if urls:
                    url = urls.pop(0)
                    start_index = input.index(url)
                    end_index = start_index + len(url)
                    output += self._escape(input[:start_index])
                    match = self.url_re.match(url)
                    if not match:
                        output += self._escape(url)
                    else:
                        if not match.group("type"):
                            url = "http://%s" % url
                        output += b'<a href="%s">%s</a>' % (url, url)
                    input = input[end_index:]
                else:
                    output += self._escape(input)
                    input = None

        output += b"</body></html>"
        return output.decode("utf-8")

    @staticmethod
    def _escape(text):
        return html.escape(text).encode("ascii", "xmlcharrefreplace")

    def unhtmlize_body(self, html_):
        # Strip this down to Markdown text
        with self.html2text_lock:
            return self.html2text.handle(html_)

