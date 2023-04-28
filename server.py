import asyncio
import re
import sys
from asyncio import AbstractServer, StreamWriter, StreamReader

import aiohttp.web
import magic


class Server:
    def __init__(self) -> None:
        self.__clients: list[asyncio.StreamWriter] = []

        self.web_app = aiohttp.web.Application()
        self.web_app.add_routes([aiohttp.web.get('/count', self.__clients_count)])

        self.m = magic.Magic()

    async def run(self, reader: StreamReader, writer: StreamWriter) -> None:
        """This is server starter. When a client is connected, he's moved to the clients list.
        The next step is to wait for messages and process them in message_handler"""

        self.__clients.append(writer)
        asyncio.create_task(self.__message_handler(reader, writer))

    async def __message_handler(self, reader: StreamReader, writer: StreamWriter) -> None:
        """Receiving the messages and check if it's correct, also check type. It should play audio on background
        when type is audio.

        Receiving the stop word will start self-closing of the server and closing up all connections"""

        async def send_all(msg: bytes) -> None:
            """Returning received message to all clients"""
            for c in self.__clients:
                c.write(msg)
                await writer.drain()

        client_message = await reader.read(1024 * 1024)  # 1 Mb
        while client_message:
            #  For checking in this case used 'magic' library that doesn't work properly on Windows
            type_obj = self.m.from_buffer(client_message)
            if re.findall(r'audio|WAVE', type_obj, re.IGNORECASE):
                asyncio.create_task(send_all(client_message))
            else:
                if re.fullmatch(rb'\W*CATASTROPHE\W*', client_message, re.IGNORECASE):
                    for client in self.__clients:
                        self.__final_close(client, safe=False)
                    return
                await send_all(client_message)
            client_message = await reader.read(1024 * 1024)

    async def __clients_count(self, request) -> aiohttp.web.Response:
        """Getting the clients count when request is '.../count'"""
        await asyncio.sleep(0.01)
        response_text = str(len(self.__clients))
        return aiohttp.web.Response(text=response_text)

    @staticmethod
    def __final_close(client, safe=True):
        """Close connection with client and exit the program.
        If safe parameter is not True, then this will cause the buffer to be clear"""
        client.close()
        if not safe:
            import gc
            for obj in gc.get_objects():
                del obj
        sys.exit(0 if safe else 1)


async def main():
    server_obj: Server = Server()

    async def server_starter(reader: StreamReader, writer: StreamWriter):
        await server_obj.run(reader, writer)

    server: AbstractServer = await asyncio.start_server(server_starter, host='localhost', port=7777)
    async with server:
        try:
            web_runner: aiohttp.web.AppRunner = aiohttp.web.AppRunner(server_obj.web_app)
            await web_runner.setup()
            web_site = aiohttp.web.TCPSite(web_runner, '', 9999)
            await web_site.start()
            await server.serve_forever()
        finally:
            server.close()
            await server.wait_closed()


if __name__ == '__main__':
    asyncio.run(main())
