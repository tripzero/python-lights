import numpy as np
import struct
import binascii


class LightParser:

    commandsMap = {}

    @staticmethod
    def command(cmd):
        def make_command(func):
            LightParser.commandsMap[cmd] = func
            return func
        return make_command


class IncompatibleProtocolException(Exception):
    def __init__(self, protocol, should_be_protocol):
        Exception.__init__(self)
        print("protocol {} should be {}".format(protocol, should_be_protocol))


class BadMessageTypeException(Exception):
    def __init__(self):
        Exception.__init__(self)
        print("message type should be bytearray")


class InvalidCommandException(Exception):
    pass


class InvalidMessageLength(Exception):
    pass


class LightProtocolCommand:
    SetColor = 0x01
    SetNumPixels = 0x02
    Clear = 0x03
    SetDebug = 0x05
    SetAllColor = 0x06
    SetSeries = 0x07


class ColorChangeSet:
    def __init__(self):
        self.changes = {}

    def append_color(self, id, color):
        self.changes[id] = color


class LightProtocol:
    """
            Light protocol follows the following frame/payload structure:

            [Header] [Payload]

            Header:

            [Protocol_Version][Payload_Length]
            [1byte][2bytes]

            Payload:
            [Command][Data]
            [1byte][...]

            Commands (@see LightProtocolCommand):

            SetColor - Set the color of an pixel
            SetNumPixels - Set number of pixels in string
            SetDebug - turn on/off debugging messages on client/server
            SetAllColor - Set all pixels in string to color
            SetSeries - Set a series of pixels in string to color


    """
    ledsDataCopy = None

    def __init__(self, leds=None, debug=False):

        self.supportsChangeColor = False
        self.changeColor = self.setColor

        """leds = LightArray2 handle.  This is only used when trying to parse."""
        self.leds = leds
        self.protocol_version = 0x01  # version 1.0
        self.debug = debug
        self.compression = False

    def debug_print(self, msg):
        if self.debug:
            print(msg)

    def updateCompress(self, ledsData):
        index = 0

        while index < len(ledsData):
            color = ledsData[index]
            startId = index
            length = 0
            for i in ledsData[index:]:
                if not np.array_equal(color, i):
                    break

                length += 1

            if length < 4:
                """if the length is less than 4, it's not worth the extra bits to send a setSeries"""
                for i in range(length):
                    self.setColor(startId + i, color)
            else:
                self.setSeries(startId, length, color)

            index += length

    def update(self, ledsData, force=False):
        if len(ledsData) == 1 or np.unique(ledsData).size == 1:
            self.setAllColor(ledsData[0])
            return

        if self.compression:
            stdDev = np.std(ledsData)

            if stdDev < len(ledsData) / 4:
                " if there's a lot of common data, we can compress the stream and break up the packets "
                return self.updateCompress(ledsData)

        if self.ledsDataCopy is None:
            self.ledsDataCopy = np.array(ledsData, copy=True)
            # self.SetNumPixels(len(self.ledsDataCopy))
            diff = self.ledsDataCopy
        else:
            diff = np.bitwise_xor(ledsData, self.ledsDataCopy)

        ledsToChange = bytearray()
        changeset = {}
        for i in range(len(diff)):
            if not np.all(np.equal(diff[i], [0, 0, 0])):
                changeset[i] = ledsData[i]

        self.setColor([*changeset], list(changeset.values()))

        self.ledsDataCopy = np.array(ledsData, copy=True)

        if force:
            self.flush()

    def send(self, msg):
        """This is intended to be overridden"""
        return msg

    def flush(self):
        """This is intended to be overriden.
           Flush any buffers."""
        pass

    def writeHeader(self, msg):
        """write header:
        [8bit][16bit]
        [protocol_version][msg_length]
        """

        header = bytearray([self.protocol_version])  # protocol version 1.0
        header.extend(struct.pack('<H', len(msg)))

        msg = header + msg

        return msg

    def setColor(self, id, color):
        """
        Command 0x01
        sets the color of a specific light

        Data:

        [Command][Number_Lights_to_set][id_1][r][g][b][id_n][r][g][b]...
        """
        header = bytearray()
        header.append(LightProtocolCommand.SetColor)

        if not isinstance(id, list):
            id = [id]

        if not isinstance(color, list):
            color = [color]

        header.extend(struct.pack('<H', len(id)))

        i = 0
        light = bytearray()

        for curr_id in id:
            light.extend(struct.pack('<H', curr_id))
            light.extend(color[i])
            i += 1

        buff = header + light

        return self.send(buff)

    def setSeries(self, startId, length, color):
        """
        Command 0x07
        sets all lights in the series starting from "startId" to "endId" to "color"

        Data:
        [0x07][startId][length][r][g][b]
        """

        buff = bytearray()
        buff.append(LightProtocolCommand.SetSeries)
        buff.extend(struct.pack('<H', startId))
        buff.extend(struct.pack('<H', length))
        buff.extend(color)

        return self.send(buff)

    def setAllColor(self, color):
        """
        Command: 0x06
        sets all colors in the array

        Data:
        [Command][r][g][b]

        """

        header = bytearray()
        header.append(LightProtocolCommand.SetAllColor)

        light = bytearray()
        light.extend(color)

        buff = header + light
        return self.send(buff)

    def clear(self):
        """
        Command: 0x03
        clear all leds

        Data:
        [Command]
        """

        header = bytearray()
        header.append(LightProtocolCommand.Clear)

        return self.send(header)

    def SetNumPixels(self, numLeds):
        buff = bytearray()
        buff.append(LightProtocolCommand.SetNumPixels)
        buff.extend(struct.pack('<H', numLeds))
        return self.send(buff)

    def setDebug(self, d):
        buff = bytearray()
        buff.append(LightProtocolCommand.SetDebug)
        buff.append(int(d))
        return self.send(buff)

    def parse(self, msg_b):
        if not isinstance(msg_b, bytearray):
            raise BadMessageTypeException()

        if self.debug:
            self.debug_print("message: {}".format(binascii.hexlify(msg_b)))

        #msg = memoryview(msg_b)
        msg = msg_b

        protocol_version = msg[0]
        msg_length = struct.unpack('<H', msg[1:3])[0]

        if protocol_version != self.protocol_version:
            raise IncompatibleProtocolException(
                protocol_version, self.protocol_version)

        msg = msg[3:]  # remove header and process all commands in message:

        if len(msg) < msg_length:
            raise InvalidMessageLength()

        while len(msg):

            cmd = msg[0]
            if cmd in LightParser.commandsMap:
                msg = LightParser.commandsMap[cmd](self, msg)

                if self.debug:
                    self.debug_print(
                        "remaining message: {}".format(binascii.hexlify(msg)))
            else:
                raise InvalidCommandException(
                    "command {0} not supported in {}".format(cmd, self.protocol_version))

    @LightParser.command(LightProtocolCommand.SetColor)
    def parseSetColor(self, msg):
        assert(len(msg) >= 6)

        numlights = struct.unpack('<H', msg[1:3])[0]

        light = 3  # start at light at position 3 in the msg
        for i in range(numlights):
            id = struct.unpack('<H', msg[light:light+2])[0]

            r = msg[light+2]
            g = msg[light+3]
            b = msg[light+4]

            self.leds.changeColor(id, [r, g, b])

            light += 5  # 5 bytes per light

        return msg[light:]

    @LightParser.command(LightProtocolCommand.Clear)
    def parseClear(self, msg):
        self.leds.clear()
        return msg[1:]

    @LightParser.command(LightProtocolCommand.SetNumPixels)
    def parseSetNumPixels(self, msg):
        numlights = struct.unpack('<H', msg[1:3])[0]

        self.leds.setLedArraySize(numlights)

        return msg[3:]

    @LightParser.command(LightProtocolCommand.SetAllColor)
    def parseSetAllLeds(self, msg):

        assert(len(msg) > 3)

        pos = 1
        r = msg[pos]
        g = msg[pos+1]
        b = msg[pos+2]

        for led in range(self.leds.ledArraySize):
            self.leds.changeColor(led, [r, g, b])

        return msg[4:]

    @LightParser.command(LightProtocolCommand.SetSeries)
    def parseSetSeries(self, msg):
        start_id = struct.unpack('<H', msg[1:3])[0]
        numlights = struct.unpack('<H', msg[3:5])[0]

        r = msg[5]
        g = msg[6]
        b = msg[7]

        i = start_id
        while i < start_id + numlights:
            self.leds.changeColor(i, [r, g, b])
            i += 1

        return msg[8:]

    @LightParser.command(LightProtocolCommand.SetDebug)
    def parseSetDebug(self, msg):
        debug = msg[1]

        self.debug = debug == 1

        return msg[2:]
