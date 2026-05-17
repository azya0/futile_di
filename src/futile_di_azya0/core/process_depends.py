from __future__ import annotations
from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Generator, AsyncGenerator, Sequence, Callable, Any

from ..depends import Depends, DependsType
from ..exceptions import DependsAsyncError, SyncContextResultError, AsyncContextResultError


class ContextResult[StateT, GeneratorT](ABC):
    @abstractmethod
    def get_state(self) -> StateT:
        pass

    @abstractmethod
    def get_generator(self) -> GeneratorT:
        pass


class SyncContextState(IntEnum):
    NO_CONTEXT = 0
    GENERATOR = 1


class SyncContextResult[T](ContextResult[SyncContextState, Generator[T]]):
    def __init__(self, value: Generator[T] | None):
        self.state = SyncContextState.NO_CONTEXT if value is None else SyncContextState.GENERATOR
        self.value = value
    
    def get_state(self) -> SyncContextState:
        return self.state
    
    def get_generator(self) -> Generator[T]:
        if self.value is None:
            raise SyncContextResultError()
        
        return self.value


def process_depends[T](depends: Depends[T]) -> tuple[SyncContextResult, T]:
    depends_type = depends.get_type()

    match(depends_type):
        case DependsType.VALUE:
            return SyncContextResult(None), depends.injected
        case DependsType.SYNC:
            return SyncContextResult(None), depends.injected()
        case DependsType.ASYNC | DependsType.ASYNC_GENERATOR:
            raise DependsAsyncError()
        case DependsType.GENERATOR:
            generator: Generator[T] = depends.injected()

            return SyncContextResult(generator), next(generator)
    
    raise BaseException(f"process_depends can't proccess DependsType: {depends_type}")


class AsyncContextState(IntEnum):
    NO_CONTEXT = 0
    GENERATOR = 1
    ASYNC_GENERATOR = 2


class AsyncContextResult[T](ContextResult[AsyncContextState, Generator[T] | AsyncGenerator[T]]):
    def __init__(
            self,
            value: AsyncGenerator[T] | Generator[T] | None,
            state: AsyncContextState | None = None,
        ):

        self.state = state if state is not None else AsyncContextState.NO_CONTEXT if value is None else AsyncContextState.ASYNC_GENERATOR
        self.value = value
    
    @staticmethod
    def from_sync[T](result: SyncContextResult[T]) -> AsyncContextResult[T]:
        return AsyncContextResult(value=result.value, state=result.state)
    
    def get_state(self) -> AsyncContextState:
        return self.state
    
    def get_generator(self) -> Generator[T] | AsyncGenerator[T]:
        if self.value is None:
            raise AsyncContextResultError()
        
        return self.value


async def process_depends_async[T](depends: Depends[T]) -> tuple[AsyncContextResult, T]:
    try:
        context_result, value = process_depends(depends)

        return AsyncContextResult.from_sync(context_result), value
    except DependsAsyncError:
        pass

    match(depends.get_type()):
        case DependsType.ASYNC:
            return AsyncContextResult(None), await depends.injected()
        case DependsType.ASYNC_GENERATOR:
            generator: AsyncGenerator[T] = depends.injected()

            context = AsyncContextResult(generator)

            return context, await anext(generator)


def process_arg_sequence[T](
        sequence: Sequence[T],
        get_arg: Callable[[T], Any],
        callback: Callable[[T, Any], None]
    ) -> Generator[tuple[T, Depends]]:

    """
    Generator, that process function's args as sequence.

    For every element of sequence we look if real_arg := get_arg(element) it instance of Depends.
    If it not, we call callback function, with element of sequence and real_arg.
    Else we yield real_arg, so it can be processed outside in sync/async scope
    """

    for arg in sequence:
        if not isinstance(real_arg := get_arg(arg), Depends):
            callback(arg, real_arg)
            continue

        yield arg, real_arg
