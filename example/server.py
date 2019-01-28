import asyncio
import socket

from async_http import app
from async_http import router
from async_http import response


async def hello(request):
    return response.text("hello-world!")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("localhost", 9999))

    rtr = router.Router()
    rtr.add("/hello", frozenset({"GET"}), hello)
    srv = app.AsyncHTTPServer(name="hello-world-server", router=rtr)
    start_serving, run_forever = srv.run(sock=sock, loop=loop)

    start_serving()
    # here you can do some additional operations before starting an infinite serving
    # can be helpful for unix sockets, etc.
    run_forever()
