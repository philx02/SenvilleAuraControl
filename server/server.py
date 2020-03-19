#!/usr/bin/python3

from subprocess import call
import asyncio
from websocketserver import WebSocketServer
from enum import Enum
import copy
import pickle
import os.path

class HpMode(Enum):
    COOLING = 0
    HEATING = 1

class HpData:
    def __init__(self):
        self.mode = HpMode.HEATING
        self.temperature_command = 23

    def __eq__(self, other): 
        if not isinstance(other, HpData):
            # don't attempt to compare against unrelated types
            return NotImplemented
        return self.mode == other.mode and self.temperature_command == other.temperature_command

def generate_message(hp_data):
    return str(hp_data.mode) + "," + str(hp_data.temperature_command)

def set_hp(hp_data):
    print(generate_message(hp_data))
    command = "heat_" if hp_data.mode == HpMode.HEATING else "cool_"
    command += str(hp_data.temperature_command)
    command += "c"
    call(["irsend", "send_once", "senville_aura", command])

class HpServer:
    def __init__(self, hp_data_pickle = None):
        self.lock = asyncio.Lock()
        self.producer_condition = asyncio.Condition(lock=self.lock)
        if hp_data_pickle is not None:
            self.hp_data = hp_data_pickle
        else:
            self.hp_data = HpData()
        self.previous_hp_data = copy.deepcopy(self.hp_data)
        self.timer = 0
        set_hp(self.hp_data)

    @asyncio.coroutine
    def init(self, websocket):
        with (yield from self.lock):
            message = generate_message(self.hp_data)
        yield from websocket.send(message)

    @asyncio.coroutine
    def produce(self, websocket, websockets):
        with (yield from self.producer_condition):
            yield from self.producer_condition.wait()
            message = generate_message(self.hp_data)
        yield from websocket.send(message)

    @asyncio.coroutine
    def consume(self, websocket, websockets):
        message = yield from websocket.recv()
        print(message)
        if message == "heating":
            with (yield from self.lock):
                self.hp_data.mode = HpMode.HEATING
                self.timer = 10
        elif message == "cooling":
            with (yield from self.lock):
                self.hp_data.mode = HpMode.COOLING
                self.timer = 10
        elif message == "minus" and self.hp_data.temperature_command > 17:
            with (yield from self.lock):
                self.hp_data.temperature_command -= 1
                self.timer = 10
        elif message == "plus" and self.hp_data.temperature_command < 30:
            with (yield from self.lock):
                self.hp_data.temperature_command += 1
                self.timer = 10
        for client in websockets:
            yield from client.send(generate_message(self.hp_data))

    @asyncio.coroutine
    def notify_clients(self):
        yield from asyncio.sleep(.1)
        with (yield from self.lock):
            if self.timer > 0:
                #print(str(self.timer))
                self.timer -= 1
                if self.timer == 0 and self.hp_data != self.previous_hp_data:
                    set_hp(self.hp_data)
                    with open("dump.bck", "wb") as file:
                        pickle.dump(self.hp_data, file)
                    self.previous_hp_data = copy.deepcopy(self.hp_data)
        asyncio.ensure_future(self.notify_clients())

def main():
    loop = asyncio.get_event_loop()

    if os.path.isfile("dump.bck"):
        with open("dump.bck", "rb") as file:
            hp_server = HpServer(pickle.load(file))
    else:
        hp_server = HpServer()

    websocket_server = WebSocketServer(hp_server.init, hp_server.consume, hp_server.produce, 8010)
    loop.run_until_complete(websocket_server.start_server)

    asyncio.ensure_future(hp_server.notify_clients())

    asyncio.get_event_loop().run_forever()

main()
