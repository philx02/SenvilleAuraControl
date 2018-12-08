import asyncio
from enum import Enum

class HpMode(Enum):
    COOLING = 0
    HEATING = 1

class HpData:
    def __init__(self):
        self.mode = HpMode.COOLING
        self.temperature_command = 23

class GenericProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.data = None
        self.lock = None
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        asyncio.ensure_future(self.__set_data(data))

    def set_the_data(self, data):
        raise NotImplementedError()

    def setup(self, data, lock):
        self.data = data
        self.lock = lock

    @asyncio.coroutine
    def __set_data(self, data):
        with (yield from self.lock):
            self.set_the_data(data)

class IrCommandProtocol(GenericProtocol):
    def set_the_data(self, data):
        self.data.mode = 1