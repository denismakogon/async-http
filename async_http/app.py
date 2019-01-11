# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging

from asyncio import CancelledError
from collections import defaultdict, deque
from inspect import getmodulename, isawaitable, stack
from traceback import format_exc

from .exceptions import AsyncHTTPException, ServerError
from .error_handler import ErrorHandler
from .request import Request
from .response import HTTPResponse, StreamingHTTPResponse
from .server import serve

logger = logging.getLogger(__name__)


class AsyncHTTPServer(object):
    def __init__(
        self,
        name=None,
        router=None,
    ):

        if name is None:
            frame_records = stack()[1]
            name = getmodulename(frame_records[1])

        self.name = name
        self.router = router
        self.request_class = Request
        self.error_handler = ErrorHandler()
        self.config = {}
        self.request_middleware = deque()
        self.response_middleware = deque()
        self.blueprints = {}
        self._blueprint_order = []
        self.debug = None
        self.sock = None
        self.listeners = defaultdict(list)
        self.is_running = False
        self.is_request_stream = False
        self.websocket_enabled = False
        self.websocket_tasks = set()

        # Register alternative method names
        self.go_fast = self.run

    async def _run_request_middleware(self, request):
        # The if improves speed.  I don't know why
        if self.request_middleware:
            for middleware in self.request_middleware:
                response = middleware(request)
                if isawaitable(response):
                    response = await response
                if response:
                    return response
        return None

    async def _run_response_middleware(self, request, response):
        if self.response_middleware:
            for middleware in self.response_middleware:
                _response = middleware(request, response)
                if isawaitable(_response):
                    _response = await _response
                if _response:
                    response = _response
                    break
        return response

    async def handle_request(self, request, write_callback, stream_callback):
        """Take a request from the HTTP Server and return a response object
        to be sent back The HTTP Server only expects a response object, so
        exception handling must be done here
        :param request: HTTP Request object
        :param write_callback: Synchronous response function to be
            called with the response as the only argument
        :param stream_callback: Coroutine that handles streaming a
            StreamingHTTPResponse if produced by the handler.
        :return: Nothing
        """
        # Define `response` var here to remove warnings about
        # allocation before assignment below.
        response = None
        cancelled = False
        try:
            # -------------------------------------------- #
            # Request Middleware
            # -------------------------------------------- #

            request.app = self
            response = await self._run_request_middleware(request)
            # No middleware results
            if not response:
                # -------------------------------------------- #
                # Execute Handler
                # -------------------------------------------- #

                # Fetch handler from router
                handler, args, kwargs, uri = self.router.get(request)

                request.uri_template = uri
                if handler is None:
                    raise ServerError(
                        (
                            "'None' was returned while requesting a "
                            "handler from the router"
                        )
                    )
                else:
                    if not getattr(handler, "__blueprintname__", False):
                        request.endpoint = self._build_endpoint_name(
                            handler.__name__
                        )
                    else:
                        request.endpoint = self._build_endpoint_name(
                            getattr(handler, "__blueprintname__", ""),
                            handler.__name__,
                        )

                # Run response handler
                response = handler(request, *args, **kwargs)
                if isawaitable(response):
                    logger.info("got response from function")
                    res = await response
                    body = res.body()
                    headers = res.context().GetResponseHeaders()
                    status = res.status()
                    response = HTTPResponse(
                        body=body, status=status,
                        headers=headers,
                        content_type=headers.get("Content-Type")
                    )
        except CancelledError:
            # If response handler times out, the server handles the error
            # and cancels the handle_request job.
            # In this case, the transport is already closed and we cannot
            # issue a response.
            response = None
            cancelled = True
        except Exception as e:
            # -------------------------------------------- #
            # Response Generation Failed
            # -------------------------------------------- #
            logger.error("Exception: ", exc_info=1)
            try:
                response = self.error_handler.response(request, e)
                if isawaitable(response):
                    response = await response
            except Exception as e:
                if isinstance(e, AsyncHTTPException):
                    response = self.error_handler.default(
                        request=request, exception=e
                    )
                elif self.debug:
                    response = HTTPResponse(
                        "Error while handling error: {}\nStack: {}".format(
                            e, format_exc()
                        ),
                        status=500,
                    )
                else:
                    response = HTTPResponse(
                        "An error occurred while handling an error", status=500
                    )
        finally:
            # -------------------------------------------- #
            # Response Middleware
            # -------------------------------------------- #
            # Don't run response middleware if response is None
            if response is not None:
                try:
                    response = await self._run_response_middleware(
                        request, response
                    )
                except CancelledError:
                    # Response middleware can timeout too, as above.
                    response = None
                    cancelled = True
                except BaseException:
                    logger.error(
                        "Exception occurred in one of response "
                        "middleware handlers", exc_info=1
                    )
            if cancelled:
                raise CancelledError()

        # pass the response to the correct callback
        if isinstance(response, StreamingHTTPResponse):
            await stream_callback(response)
        else:
            write_callback(response)

    def _build_endpoint_name(self, *parts):
        parts = [self.name, *parts]
        return ".".join(parts)

    def run(self, sock=None, loop=None):
        return serve(
            self.handle_request, ErrorHandler(),
            sock=sock, loop=loop
        )
