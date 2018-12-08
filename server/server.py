#!/usr/bin/python3

import asyncio
from websocketserver import WebSocketServer

from datetime import datetime

from data_collection import *
from create_socket import create_socket

def generate_message(hp_data):
    return hp_data.mode + "," + hp_data.temperature_command

class HpServer:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.producer_condition = asyncio.Condition(lock=self.lock)
        self.hp_data = HpData()

    @asyncio.coroutine
    def init(self, websocket):
        with (yield from self.lock):
            message = generate_message(self.hp_data)
        yield from websocket.send(message)

    @asyncio.coroutine
    def produce(self, websocket):
        with (yield from self.producer_condition):
            yield from self.producer_condition.wait()
            message = generate_message(self.hp_data)
        yield from websocket.send(message)

    @asyncio.coroutine
    def consume(self, websocket):
        message = yield from websocket.recv()
        split = message.split(",")
        if len(split) == 2:
            if split[0] == "set_mode":
                self.hp_data.mode = HpMode(split[1])
            elif split[0] == "set_temperature_command":
                self.hp_data.temperature_command = HpMode(split[1])

    @asyncio.coroutine
    def notify_clients(self):
        with (yield from self.producer_condition):
            self.producer_condition.notify_all()
        yield from asyncio.sleep(1)
        asyncio.ensure_future(self.notify_clients())

def main():
    loop = asyncio.get_event_loop()
    hp_server = HpServer()

    ic_transport, ic_protocol = loop.run_until_complete(loop.create_datagram_endpoint(IrCommandProtocol, sock=create_socket("127.0.0.1", 10000)))
    ic_protocol.setup(hp_server.hp_data, hp_server.lock)

    websocket_server = WebSocketServer(hp_server.init, hp_server.consume, hp_server.produce, 8011)
    loop.run_until_complete(websocket_server.start_server)

    asyncio.ensure_future(hp_server.notify_clients())

    asyncio.get_event_loop().run_forever()

main()
