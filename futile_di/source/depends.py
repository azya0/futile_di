from enum import Enum
from inspect import iscoroutinefunction, isasyncgenfunction, isgeneratorfunction, isfunction
from typing import Callable


class DependsType(Enum):
    VALUE = 0,
    SYNC = 1,
    ASYNC = 2,
    GENERATOR = 3,
    ASYNC_GENERATOR = 4,


class Depends[T]:
    def _get_type(self) -> DependsType:
        if isasyncgenfunction(self.injected):
            return DependsType.ASYNC_GENERATOR
        
        if isgeneratorfunction(self.injected):
            return DependsType.GENERATOR
        
        if iscoroutinefunction(self.injected):
            return DependsType.ASYNC
        
        if isfunction(self.injected):
            return DependsType.SYNC

        return DependsType.VALUE

    def __init__(self, injected: Callable[[], T]):
        self.injected = injected

        self.__depends_type = self._get_type()
    
    def get_type(self) -> DependsType:
        return self.__depends_type
