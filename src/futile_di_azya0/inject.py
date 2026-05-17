from contextlib import suppress
from functools import wraps
from inspect import iscoroutinefunction, signature
from typing import Any, Generator, AsyncGenerator

from .core.process_depends import (
    process_depends, SyncContextState,
    process_depends_async, AsyncContextState,
    process_arg_sequence
)
from .depends import Depends


class ContextHolder:
    def __init__(self):
        self.__sync_context:  list[Generator] = []
        self.__async_context: list[AsyncGenerator] = []

    def add_sync_context(self, context: Generator):
        self.__sync_context.append(context)
    
    def add_async_context(self, context: AsyncGenerator):
        self.__async_context.append(context)
    
    def close_sync(self):
        for context in self.__sync_context:
            try:
                next(context)
            except StopIteration:
                pass
        
        self.__sync_context.clear()

    async def close_async(self):
        self.close_sync()

        for context in self.__async_context:
            try:
                await anext(context)
            except StopAsyncIteration:
                pass
        
        self.__async_context.clear()


def inject(old_function):
    old_function_sig = signature(old_function)

    def update_kwargs_with_defaults(args, kwargs) -> tuple[tuple[Any], dict[str, Any]]:
        bound = old_function_sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        
        return bound.args, bound.kwargs

    def process_args_kwargs(
            args: tuple[Any], kwargs: dict[str, Any],
            processed_args: list[Any], processed_kwargs: dict[str, Any]
        ) -> Generator[Depends, Any]:
        
        args_generator = process_arg_sequence(
            sequence=args,
            get_arg=lambda value: value,
            callback=lambda _, result : processed_args.append(result)
        )

        for _, depends in args_generator:
            result_arg = yield depends

            processed_args.append(result_arg)

        kwargs_generator = process_arg_sequence(
            sequence=kwargs.items(),
            get_arg=lambda items: items[1],
            callback=lambda items, result : processed_kwargs.__setitem__(items[0], result)
        )

        for key, depends in kwargs_generator:
            result_kwarg = yield depends

            processed_kwargs[key] = result_kwarg
    
    @wraps(old_function)
    def new_function(*args, **kwargs):
        context_holder: ContextHolder = ContextHolder()
        processed_args:     list[Any] = []
        processed_kwargs:   dict[str, Any] = {}
        
        args, kwargs = update_kwargs_with_defaults(args, kwargs)

        depends_generator = process_args_kwargs(args, kwargs, processed_args, processed_kwargs)

        for depends in depends_generator:
            context, value = process_depends(depends)

            if context.get_state() == SyncContextState.GENERATOR:
                context_holder.add_sync_context(context.get_generator())
            
            with suppress(StopIteration):
                depends_generator.send(value)

        result = old_function(*processed_args, **processed_kwargs)

        context_holder.close_sync()
        
        return result
    
    @wraps(old_function)
    async def new_async_function(*args, **kwargs):
        context_holder: ContextHolder = ContextHolder()
        processed_args:     list[Any] = []
        processed_kwargs:   dict[str, Any] = {}
        
        args, kwargs = update_kwargs_with_defaults(args, kwargs)

        depends_generator = process_args_kwargs(args, kwargs, processed_args, processed_kwargs)

        for depends in depends_generator:
            context, value = await process_depends_async(depends)

            context_state = context.get_state()

            if context_state != AsyncContextState.NO_CONTEXT:
                generator = context.get_generator()

                if context_state == AsyncContextState.GENERATOR:
                    context_holder.add_sync_context(generator)
                else:
                    context_holder.add_async_context(generator)

            with suppress(StopIteration):
                depends_generator.send(value)
        
        result = await old_function(*processed_args, **processed_kwargs)

        await context_holder.close_async()

        return result

    if iscoroutinefunction(old_function):
        return new_async_function

    return new_function
