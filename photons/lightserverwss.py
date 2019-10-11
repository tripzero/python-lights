import asyncio
from wss.wssserver import Server, server_main


class LightServerWss(Server):
    def __init__(self, leds=None, port=None, iface="localhost",
                 useSsl=False, sslCert="server.crt",
                 sslKey="server.key", debug=False):
        self.leds = leds
        self.port = port
        self.iface = iface

        # Keep about 5 seconds worth of data
        self.queue = asyncio.Queue(maxsize=self.leds.fps * 5)

        self.parser = LightProtocol(leds=self.leds, debug=debug)

        Server.__init__(self, port=port, useSsl=useSsl,
                        sslCert=sslCert, sslKey=sslKey)

        asyncio.get_event_loop().create_task(self._processQueue())

    def onBinaryMessage(self, msg, fromClient):
        data = bytearray()
        data.extend(msg)

        """
        self.print_debug("message length: {}".format(len(data)))
        self.print_debug("message data: {}".format(hexlify(data)))
        """

        try:
            self.queue.put_nowait(data)
        except asyncio.QueueFull:
            pass  # drop message

    @asyncio.coroutine
    def _processQueue(self):
        while True:

            data = yield from self.queue.get()
            self.parser.parse(data)

            yield from asyncio.sleep(1 / self.leds.fps)


if __name__ == "__main__":
    from photons import LightArray2, OpenCvSimpleDriver, DummyDriver

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--wss', dest="wss",
                        help="use wss.", action='store_true')
    parser.add_argument('--udp', dest="udp",
                        help="use udp.", action='store_true')

    args, unknown = parser.parse_known_args()

    num_lights = 200

    leds = LightArray2(num_lights, OpenCvSimpleDriver(opengl=True), fps=60)

    sc = LightServer

    if args.wss:
        sc = LightServerWss

    if args.udp:
        sc = LightServerUdp

    server = server_main(ServerClass=sc, leds=leds)

    server.start()

    asyncio.get_event_loop().run_forever()

    server.close()
