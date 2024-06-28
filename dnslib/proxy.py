# -*- coding: utf-8 -*-

from __future__ import print_function

import socket
import struct
import argparse
import time

from dnslib import DNSRecord, RCODE
from dnslib.server import DNSServer, DNSHandler, BaseResolver, DNSLogger


class ProxyResolver(BaseResolver):
    """
    Proxy resolver - passes all requests to upstream DNS server and
    returns response
    """

    def __init__(self, address, port, timeout=5):
        self.address = address
        self.port = port
        self.timeout = timeout

    def resolve(self, request, handler):
        try:
            if handler.protocol == 'udp':
                proxy_r = request.send(self.address, self.port,
                                       timeout=self.timeout)
            else:
                proxy_r = request.send(self.address, self.port,
                                       tcp=True, timeout=self.timeout)
            reply = DNSRecord.parse(proxy_r)
        except socket.timeout:
            reply = request.reply()
            reply.header.rcode = getattr(RCODE, 'NXDOMAIN')

        return reply


class CustomDNSServer(DNSServer):
    """
    Custom DNSServer to ensure resolver and logger attributes are available
    """

    def __init__(self, resolver, address="0.0.0.0", port=53, tcp=False, logger=None, handler=DNSHandler):
        super(CustomDNSServer, self).__init__(resolver, address, port, tcp, logger, handler)
        self.resolver = resolver
        self.logger = logger


class PassthroughDNSHandler(DNSHandler):
    """
    Modify DNSHandler logic to send directly to upstream DNS server
    rather than decoding/encoding packet and passing to Resolver
    """

    def get_reply(self, data):
        host, port = self.server.resolver.address, self.server.resolver.port

        request = DNSRecord.parse(data)
        self.log_request(request)

        if self.protocol == 'tcp':
            data = struct.pack("!H", len(data)) + data
            response = send_tcp(data, host, port)
            response = response[2:]
        else:
            response = send_udp(data, host, port)

        reply = DNSRecord.parse(response)
        self.log_reply(reply)

        return response

    def log_request(self, request):
        self.server.logger.log("Request: %s" % str(request))

    def log_reply(self, reply):
        self.server.logger.log("Reply: %s" % str(reply))


def send_tcp(data, host, port):
    """
    Helper function to send/receive DNS TCP request
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((host, port))
        sock.sendall(data)
        response = sock.recv(8192)
        length = struct.unpack("!H", response[:2])[0]
        while len(response) - 2 < length:
            response += sock.recv(8192)
    return response


def send_udp(data, host, port):
    """
    Helper function to send/receive DNS UDP request
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(data, (host, port))
        response, _ = sock.recvfrom(8192)
    return response


if __name__ == '__main__':
    p = argparse.ArgumentParser(description="DNS Proxy")
    p.add_argument("--port", "-p", type=int, default=53,
                   metavar="<port>",
                   help="Local proxy port (default: 53)")
    p.add_argument("--address", "-a", default="",
                   metavar="<address>",
                   help="Local proxy listen address (default: all)")
    p.add_argument("--upstream", "-u", default="8.8.8.8:53",
                   metavar="<dns server:port>",
                   help="Upstream DNS server:port (default: 8.8.8.8:53)")
    p.add_argument("--tcp", action='store_true', default=False,
                   help="TCP proxy (default: UDP only)")
    p.add_argument("--timeout", "-o", type=float, default=5,
                   metavar="<timeout>",
                   help="Upstream timeout (default: 5s)")
    p.add_argument("--passthrough", action='store_true', default=False,
                   help="Don't decode/re-encode request/response (default: off)")
    p.add_argument("--log", default="request,reply,truncated,error",
                   help="Log hooks to enable (default: request,reply,truncated,error)")
    p.add_argument("--log-prefix", action='store_true', default=False,
                   help="Log prefix (timestamp/handler/resolver) (default: False)")
    args = p.parse_args()

    args.dns, _, args.dns_port = args.upstream.partition(':')
    args.dns_port = int(args.dns_port or 53)

    print("Starting Proxy Resolver (%s:%d -> %s:%d) [%s]" % (
        args.address or "*", args.port,
        args.dns, args.dns_port,
        "UDP/TCP" if args.tcp else "UDP"))

    resolver = ProxyResolver(args.dns, args.dns_port, args.timeout)
    handler = PassthroughDNSHandler if args.passthrough else DNSHandler
    logger = DNSLogger(args.log, args.log_prefix)
    udp_server = CustomDNSServer(resolver,
                                 port=args.port,
                                 address=args.address,
                                 logger=logger,
                                 handler=handler)
    udp_server.start_thread()

    if args.tcp:
        tcp_server = CustomDNSServer(resolver,
                                     port=args.port,
                                     address=args.address,
                                     tcp=True,
                                     logger=logger,
                                     handler=handler)
        tcp_server.start_thread()

    while udp_server.isAlive():
        time.sleep(1)
