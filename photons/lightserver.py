import asyncio
from photons import LightProtocol


def server_main(ServerClass, **kwargs):

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--ssl', dest="usessl",
                        help="use ssl.", action='store_true')
    parser.add_argument('--debug', dest="debug",
                        help="turn on debugging.", action='store_true')
    parser.add_argument('--sslcert', dest="sslcert",
                        default="server.crt", nargs=1, help="ssl certificate")
    parser.add_argument('--sslkey', dest="sslkey",
                        default="server.key", nargs=1, help="ssl key")
    parser.add_argument('--port', help="port of server", default=9000)

    args, unknown = parser.parse_known_args()

    if args.port:
        kwargs["port"] = args.port

    s = ServerClass(useSsl=args.usessl, **kwargs)
    s.debug = args.debug

    return s


class LightServer(asyncio.Protocol):

    def __init__(self, leds, port, iface="localhost", debug=False, **kwargs):

        self.leds = leds
        self.port = port
        self.iface = iface
        self.debug = debug
        self.parser = LightProtocol(leds=self.leds, debug=debug)
        self.queue = asyncio.Queue(maxsize=self.leds.fps * 5)

        asyncio.get_event_loop().create_task(self._processQueue())

    def start(self):
        loop = asyncio.get_event_loop()

        factory = loop.create_server(lambda: self,
                                     host=self.iface, port=self.port)

        self.server = loop.run_until_complete(factory)

    def print_debug(self, msg):
        if self.debug:
            print(msg)

    def connection_made(self, transport):
        # we may have only one client
        try:
            self.print_debug("new connection!")

            self.client_writer = transport

        except Exception:
            import traceback
            import sys
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
            traceback.print_exception(exc_type, exc_value, exc_traceback,
                                      limit=8, file=sys.stdout)

    def data_received(self, data):
        self.print_debug("new data received")

        try:
            self.queue.put_nowait(bytearray(data))
        except asyncio.QueueFull:
            pass  # drop message

    @asyncio.coroutine
    def _processQueue(self):
        while True:

            data = yield from self.queue.get()
            self.parser.parse(data)

            yield from asyncio.sleep(1 / self.leds.fps)

    def close(self):
        self.server.close()
        asyncio.get_event_loop().run_until_complete(
            self.server.wait_closed())


class LightServerUdp(LightServer):

    def __init__(self, *args, **kwargs):
        LightServer.__init__(self, *args, **kwargs)

    def start(self):
        loop = asyncio.get_event_loop()

        factory = loop.create_datagram_endpoint(lambda: self,
                                                local_addr=(self.iface,
                                                            self.port))

        self.server, protocol = loop.run_until_complete(factory)

    def datagram_received(self, data, addr):
        LightServer.data_received(self, data)


if __name__ == "__main__":
    from photons import LightArray2, OpenCvSimpleDriver

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--udp', dest="udp",
                        help="use udp.", action='store_true')

    args, unknown = parser.parse_known_args()

    num_lights = 200

    leds = LightArray2(num_lights, OpenCvSimpleDriver(opengl=True), fps=60)

    sc = LightServer

    if args.udp:
        sc = LightServerUdp

    server = server_main(ServerClass=sc, leds=leds)

    server.start()

    asyncio.get_event_loop().run_forever()

    server.close()
