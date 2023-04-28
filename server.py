import asyncio
from asyncio import AbstractServer, StreamWriter, StreamReader

import aiohttp.web
from aiohttp import ClientSession


class Server:
    pass


async def main():
    server_obj = Server()

    async def server_starter(reader: StreamReader, writer: StreamWriter):
        await server_obj.run(reader, writer)

    server: AbstractServer = await asyncio.start_server(server_starter, host='localhost', port=7777)
    async with server:
        try:
            web_runner = aiohttp.web.AppRunner(server_obj.web_app)
            await web_runner.setup()
            web_site = aiohttp.web.TCPSite(web_runner, '', 9999)
            await web_site.start()
            await server.serve_forever()
        finally:
            server.close()
            await server.wait_closed()


if __name__ == '__main__':
    asyncio.run(main())
