from __future__ import annotations
from abc import ABC, abstractmethod
from contextlib import suppress
from enum import IntEnum
from typing import Generator, AsyncGenerator, Sequence, Callable, Any
from queue import Queue

from ..depends import Depends, DependsType
from ..exceptions import (
    DependsAsyncError, SyncContextResultError,
    AsyncContextResultError, DependsValueWrappeUnprocessedError,
    DependsValueWrappeNoNameError
)


class DependsValueWrapper:
    def __init__(self, depends: Depends, name: str | None = None):
        self.name:              str | None = name
        self.wrapped_depends:   Depends = depends
        
        self.__is_value_got:    bool = False
        self.__value:           Any | None = None
        
        self.depends:           list[DependsValueWrapper] = []
    
    def get_depend(self) -> Depends:
        return self.wrapped_depends
    
    def is_processed(self) -> bool:
        return self.__is_value_got
    
    def get_value(self) -> Any:
        if not self.is_processed():
            raise DependsValueWrappeUnprocessedError()
        
        return self.__value
    
    def add_depends(self, depends: DependsValueWrapper):
        self.depends.append(depends)

    def get_kwargs(self) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for depend in self.depends:
            if depend.name is None:
                raise DependsValueWrappeNoNameError(depend.wrapped_depends)
            
            result.__setitem__(depend.name, depend.get_value())
        
        return result
    
    def get_depends_to_process(self) -> Generator[tuple[Depends, dict[str, Any]], Any, None]:
        self.__value = yield (self.wrapped_depends, self.get_kwargs())
        self.__is_value_got = True


def get_depends_with_nasted(depends: Depends) -> list[DependsValueWrapper]:
    process_queue = Queue[DependsValueWrapper]()
    process_queue.put_nowait(DependsValueWrapper(depends))
    result_stack: list[DependsValueWrapper] = []

    while not process_queue.empty():
        current_depends = process_queue.get_nowait()

        result_stack.append(current_depends)

        for name, pure_depends in current_depends.get_depend().get_nasted_depends():
            new_depends = DependsValueWrapper(pure_depends, name)
            
            current_depends.add_depends(new_depends)

            process_queue.put_nowait(new_depends)
    
    return result_stack


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


def process_depend[T: Any](depends: Depends[T], kwargs: dict[str, Any]) -> tuple[SyncContextResult, T]:
    depends_type = depends.get_type()

    match(depends_type):
        case DependsType.VALUE:
            return SyncContextResult(None), depends.injected
        case DependsType.SYNC:
            return SyncContextResult(None), depends.injected(**kwargs)
        case DependsType.ASYNC | DependsType.ASYNC_GENERATOR:
            raise DependsAsyncError()
        case DependsType.GENERATOR:
            generator: Generator[T] = depends.injected(**kwargs)

            return SyncContextResult(generator), next(generator)
    
    raise BaseException(f"process_depends can't proccess DependsType: {depends_type}")


def process_depends[T](depends: Depends[T]) -> tuple[list[SyncContextResult], T]:
    depends_stack = get_depends_with_nasted(depends)

    context_result: list[SyncContextResult] = []
    
    result_wrapped_depends = depends_stack[0]

    for wrapped_depends in depends_stack[::-1]:
        generator = wrapped_depends.get_depends_to_process()

        pure_depends, kwargs = next(generator)

        context, value = process_depend(pure_depends, kwargs)

        with suppress(StopIteration):
            generator.send(value)

        context_result.append(context)
    
    return context_result, result_wrapped_depends.get_value()


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


async def process_depend_async[T](depends: Depends[T], kwargs: dict[str, Any]) -> tuple[AsyncContextResult, T]:
    try:
        context_result, value = process_depend(depends, kwargs)

        return AsyncContextResult.from_sync(context_result), value
    except DependsAsyncError:
        pass

    match(depends.get_type()):
        case DependsType.ASYNC:
            return AsyncContextResult(None), await depends.injected(**kwargs)
        case DependsType.ASYNC_GENERATOR:
            generator: AsyncGenerator[T] = depends.injected(**kwargs)

            context = AsyncContextResult(generator)

            return context, await anext(generator)


async def process_depends_async[T](depends: Depends[T]) -> tuple[list[AsyncContextResult], T]:
    depends_stack = get_depends_with_nasted(depends)

    context_result: list[AsyncContextResult] = []
    
    result_wrapped_depends = depends_stack[0]

    for wrapped_depends in depends_stack[::-1]:
        generator = wrapped_depends.get_depends_to_process()

        pure_depends, kwargs = next(generator)

        context, value = await process_depend_async(pure_depends, kwargs)

        with suppress(StopIteration):
            generator.send(value)

        context_result.append(context)
    
    return context_result, result_wrapped_depends.get_value()


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
