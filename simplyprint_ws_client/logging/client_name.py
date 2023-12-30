from typing import TYPE_CHECKING, List
from typing_extensions import Self

from sympy import im

if TYPE_CHECKING:
    from ..client import Client
    from ..config import Config

class ClientName(str):
    stack: List[str]
    config: 'Config'

    def __new__(cls, config: 'Config') -> Self:
        return super().__new__(cls, config.unique_id)
    
    def __init__(self, config: 'Config') -> None:
        self.config = config
        self.stack = []

    def __str__(self) -> str:
        return ".".join([self.config.unique_id] + self.stack)
    
    def __hash__(self) -> int:
        return hash(str(self))

    def copy(self) -> Self:
        return ClientName(self.config).pushAll(self.stack)
    
    def pushAll(self, names: List[str]) -> Self:
        for name in names:
            self.push(name)
        return self

    def push(self, name: str) -> Self:
        self.stack.append(name)
        return self
    
    def pop(self) -> Self:
        self.stack.pop()
        return self
    
    def peek(self) -> str | None:
        if len(self.stack) == 0:
            return None
        
        return self.stack[-1]
    
    def getConfig(self) -> 'Config':
        return self.config
    
    def getChild(self, suffix: str) -> Self:
        return self.copy().push(suffix)

    @staticmethod
    def from_client(client: 'Client') -> Self:
        return ClientName(client.config)