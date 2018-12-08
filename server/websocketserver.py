import asyncio
import websockets

class WebSocketServer:
    def __init__(self, on_connect, consumer_handler, producer_handler, port):
        self.on_connect = on_connect
        self.consume = consumer_handler
        self.produce = producer_handler
        self.connected = set()
        self.start_server = websockets.serve(self.handler, '0.0.0.0', port)

    @asyncio.coroutine
    def consumer_handler(self, websocket):
        while True:
            yield from self.consume(websocket)

    @asyncio.coroutine
    def producer_handler(self, websocket):
        while True:
            yield from self.produce(websocket)

    @asyncio.coroutine
    def handler(self, websocket, path):
        print("client connected")
        # Register.
        self.connected.add(websocket)
        try:
            yield from self.on_connect(websocket)
            consumer_task = asyncio.async(self.consumer_handler(websocket))
            producer_task = asyncio.async(self.producer_handler(websocket))
            done, pending = yield from asyncio.wait(
                [consumer_task, producer_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
        finally:
            # Unregister.
            self.connected.remove(websocket)
