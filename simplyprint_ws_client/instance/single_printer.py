from typing import Iterable, Optional, Union

from simplyprint_ws_client.const import TEST_WEBSOCKET_URL

from ..client import Client
from ..connection import ConnectionConnectedEvent, ConnectionReconnectEvent
from ..events.client_events import MachineDataEvent, StateChangeEvent
from .instance import Instance, TClient, TConfig


class SinglePrinter(Instance[TClient, TConfig]):
    client: Optional[Client[TConfig]] = None

    async def add_client(self, client: TClient) -> None:
        self.connection.set_url(f"{TEST_WEBSOCKET_URL}/p/{client.config.id}/{client.config.token}")
        self.client = client

    def get_client(self, _: TConfig) -> Union[TClient, None]:
        return self.client

    def get_clients(self) -> Iterable[TClient]:
        return [ self.client ]

    def has_client(self, client: TClient) -> bool:
        return self.client == client

    async def remove_client(self, client: TClient) -> None:
        if not self.has_client(client):
            return 
        
        self.client = None

    def should_connect(self) -> bool:
        return not self.client is None

    async def on_connect(self, _: ConnectionConnectedEvent):
        await self.consume_backlog(self.client_event_backlog, self.on_client_event)

    async def on_reconnect(self, _: ConnectionReconnectEvent):
        # Mark certain events to always be sent to the server
        self.client.printer.mark_event_as_dirty(MachineDataEvent)
        self.client.printer.mark_event_as_dirty(StateChangeEvent)

        await self.consume_backlog(self.client_event_backlog, self.on_client_event)