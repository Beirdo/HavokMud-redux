import logging
import stackless

import dns.resolver
import dns.reversename

logger = logging.getLogger(__name__)


class DNSRequest(object):
    def __init__(self, ipaddress):
        self.ipaddress = ipaddress
        self.channel = stackless.channel()


class DNSLookup(object):
    def __init__(self):
        self.in_channel = stackless.channel()

        stackless.tasklet(self.dns_loop)()

    def dns_loop(self):
        while True:
            request = self.in_channel.receive()
            stackless.tasklet(self.dns_resolve)(request)

    def dns_resolve(self, request):
        retval = None
        addr = ""
        try:
            addr = dns.reversename.from_address(request.ipaddress)
        except Exception:
            retval = "invalid.host.name"

        answer = []
        if not retval:
            try:
                answer = dns.resolver.query(addr, "PTR")
            except Exception:
                retval = "unknown.host.name"

        if not retval:
            hostnames = [rdata for rdata in answer]
            retval = hostnames.pop(0)

        request.channel.send(retval)

    def do_reverse_dns(self, ipaddr):
        request = DNSRequest(ipaddr)
        self.in_channel.send(request)
        return request.channel.receive()
