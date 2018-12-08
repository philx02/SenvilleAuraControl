#!/usr/bin/python3

import asyncio
from websocketserver import WebSocketServer

from datetime import datetime

from data_collection import *
from create_socket import create_socket

class FermDataSnapshot:
    def __init__(self, timestamp, ferm_data):
        self.timestamp = timestamp
        self.wort_temperature = ferm_data.wort_temperature.get_mean()
        self.chamber_temperature = ferm_data.chamber_temperature.get_mean()
        self.chamber_humidity = ferm_data.chamber_humidity.get_mean()
        self.wort_density = ferm_data.wort_density.get_mean()
        self.cooling_status = ferm_data.cooling_status
    
    def serialize(self):
        return str(self.timestamp) + ",%.2f" % self.wort_temperature + ",%.2f" % self.chamber_temperature + ",%.2f" % self.chamber_humidity + ",%.2f" % self.wort_density + "," + ("1" if self.cooling_status else "0")

def generate_message(ferm_data):
    return "now_data|%.2f" % ferm_data.wort_temperature.get_mean() + "," + "%.2f" % ferm_data.chamber_temperature.get_mean() + "," + "%.2f" % ferm_data.chamber_humidity.get_mean() + "," + "%.2f" % ferm_data.wort_density.get_mean() + "," + ("1" if ferm_data.cooling_status else "0")

class FermServer:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.historical_lock = asyncio.Lock()
        self.producer_condition = asyncio.Condition(lock=self.lock)
        self.ferm_data = FermData()
        self.historical_data = []

    @asyncio.coroutine
    def init(self, websocket):
        with (yield from self.lock):
            message = generate_message(self.ferm_data)
        yield from websocket.send(message)

    @asyncio.coroutine
    def produce(self, websocket):
        with (yield from self.producer_condition):
            yield from self.producer_condition.wait()
            message = generate_message(self.ferm_data)
        yield from websocket.send(message)

    @asyncio.coroutine
    def consume(self, websocket):
        message = yield from websocket.recv()
        if message == "get_historical_data":
            response = "historical_data|"
            with (yield from self.historical_lock):
                for data_point in self.historical_data:
                    response += data_point.serialize() + ";"
            yield from websocket.send(response)

    @asyncio.coroutine
    def notify_clients(self):
        with (yield from self.producer_condition):
            self.producer_condition.notify_all()
        yield from asyncio.sleep(1)
        asyncio.ensure_future(self.notify_clients())

    @asyncio.coroutine
    def store_historical_data(self):
        yield from asyncio.sleep(60)
        with (yield from self.lock):
            with (yield from self.historical_lock):
                self.historical_data.append(FermDataSnapshot(int(datetime.now().timestamp()), self.ferm_data))
        asyncio.ensure_future(self.store_historical_data())

def main():
    loop = asyncio.get_event_loop()
    ferm_server = FermServer()

    wt_transport, wt_protocol = loop.run_until_complete(loop.create_datagram_endpoint(WortTemperatureProtocol, sock=create_socket(MCAST_GRP, THERMOCOUPLE_PORT)))
    wt_protocol.setup(ferm_server.ferm_data, ferm_server.lock)

    websocket_server = WebSocketServer(ferm_server.init, ferm_server.consume, ferm_server.produce, 8011)
    loop.run_until_complete(websocket_server.start_server)

    asyncio.ensure_future(ferm_server.notify_clients())
    asyncio.ensure_future(ferm_server.store_historical_data())

    asyncio.get_event_loop().run_forever()

main()
