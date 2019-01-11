# Minimalistic async HTTP server

This framework was inspired by [sanic](https://github.com/huge-success/sanic) framework.
This framework designed to be fast and be capable to start within 1.5 seconds at max (see [cold start problem](https://medium.com/@denismakogon/investigating-pythons-performance-issue-cold-start-8ebf443a8a20)).

## How to install

```bash
pip install async-http-minimal
```

## Example

```python
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
```
