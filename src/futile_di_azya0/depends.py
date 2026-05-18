from __future__ import annotations
from enum import Enum
from inspect import iscoroutinefunction, isasyncgenfunction, isgeneratorfunction, isfunction, unwrap
from typing import Callable
from inspect import signature, Parameter, Signature


class DependsType(Enum):
    VALUE = 0,
    SYNC = 1,
    ASYNC = 2,
    GENERATOR = 3,
    ASYNC_GENERATOR = 4,


class Depends[D: dict[str, Depends], T]:
    def _get_type(self) -> DependsType:
        injected = unwrap(self.injected)

        if isasyncgenfunction(injected):
            return DependsType.ASYNC_GENERATOR
        
        if isgeneratorfunction(injected):
            return DependsType.GENERATOR
        
        if iscoroutinefunction(injected):
            return DependsType.ASYNC
        
        if isfunction(injected):
            return DependsType.SYNC

        return DependsType.VALUE

    @staticmethod
    def __get_nested_depends(signature: Signature) -> list[tuple[str, Depends]]:
        depends_queue: list[tuple[str, Depends]] = []
        
        for name, param in signature.parameters.items():
            value = param.default

            if value != Parameter.empty and isinstance(value, Depends):
                depends_queue.append((name, param.default))
        
        return depends_queue

    def __init__(self, injected: Callable[[D], T]):
        """
        Inside the Callable injected either
        there are Depends as default kwarg
        or there are no args or kwargs at all 
        """

        self.injected = injected

        self.__depends_type = self._get_type()
        
        self.__nasted_depends = self.__get_nested_depends(
            signature(self.injected)
        ) if self.__depends_type != DependsType.VALUE else []

    def get_type(self) -> DependsType:
        return self.__depends_type

    def get_nasted_depends(self) -> list[tuple[str, Depends]]:
        return self.__nasted_depends
