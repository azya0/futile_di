from functools import wraps
from inspect import isasyncgen, iscoroutinefunction, signature
from typing import Any, Generator, AsyncGenerator, Sequence, Callable

from .depends import Depends, DependsType


class DependsAsyncError(ValueError):
    def __init__(self):
        super().__init__("can't process async depends in sync wrapped function")


def process_depends[T](depends: Depends[T]) -> tuple[Generator[T] | None, T]:
    depends_type = depends.get_type()

    match(depends_type):
        case DependsType.VALUE:
            return None, depends.injected
        case DependsType.SYNC:
            return None, depends.injected()
        case DependsType.ASYNC | DependsType.ASYNC_GENERATOR:
            raise DependsAsyncError()
        case DependsType.GENERATOR:
            generator: Generator[T] = depends.injected()

            return generator, next(generator)
    
    raise BaseException(f"process_depends can't proccess DependsType: {depends_type}")


async def process_depends_async[T](depends: Depends[T]) -> tuple[AsyncGenerator[T] | None, T]:
    try:
        return process_depends(depends)
    except DependsAsyncError:
        pass

    match(depends.get_type()):
        case DependsType.ASYNC:
            return None, await depends.injected()
        case DependsType.ASYNC_GENERATOR:
            generator: AsyncGenerator[T] = depends.injected()

            return generator, await anext(generator)


def inject(old_function):
    context_holder:     list[Generator | AsyncGenerator] = []
    
    def close_context():
        for context in context_holder:
            try:
                next(context)
            except StopIteration:
                pass
        
        context_holder.clear()
    
    async def close_context_async():
        for context in context_holder:
            if isasyncgen(context):
                try:
                    await anext(context)
                except StopAsyncIteration:
                    pass

                continue

            try:
                next(context)
            except StopIteration:
                pass
        
        context_holder.clear()

    old_function_sig = signature(old_function)

    def update_kwargs_with_defaults(args, kwargs) -> tuple[tuple[Any], dict[str, Any]]:
        bound = old_function_sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        
        return bound.args, bound.kwargs

    def process_args_kwargs(
            args: tuple[Any], kwargs: dict[str, Any],
            processed_args: list[Any], processed_kwargs: dict[str, Any]
        ) -> Generator[Depends, tuple[Any, Any]]:
        def process_arg[T](arg: Any) -> Generator[Depends[T], tuple[Any, T], Any | T]:
            if not isinstance(arg, Depends):
                return arg
            
            context, value = yield arg
            
            if context is not None:
                context_holder.append(context)
            
            return value

        def process_sequence[T, R](
                sequence: Sequence[T],
                get_arg: Callable[[T], R],
                callback: Callable[[T, R], None]
            ) -> Generator[Depends, tuple[Any, Any], None]:
            for arg in sequence:
                generator = process_arg(get_arg(arg))

                try:
                    depends = next(generator)

                    result = yield depends

                    generator.send(result)

                    next(generator)
                except StopIteration as exception:
                    callback(arg, exception.value)

        args_generator = process_sequence(
            sequence=args,
            get_arg=lambda value: value,
            callback=lambda _, result : processed_args.append(result)
        )

        try:
            while True:
                result = yield next(args_generator)

                args_generator.send(result)
        except StopIteration:
            pass

        kwargs_generator = process_sequence(
            sequence=kwargs.items(),
            get_arg=lambda items: items[1],
            callback=lambda items, result : processed_kwargs.__setitem__(items[0], result)
        )

        try:
            while True:
                result = yield next(kwargs_generator)

                kwargs_generator.send(result)
        except StopIteration:
            pass
    
    @wraps(old_function)
    def new_function(*args, **kwargs):
        processed_args:     list[Any] = []
        processed_kwargs:   dict[str, Any] = {}
        
        args, kwargs = update_kwargs_with_defaults(args, kwargs)

        generator = process_args_kwargs(args, kwargs, processed_args, processed_kwargs)

        try:
            while True:
                to_process = next(generator)

                generator.send(process_depends(to_process))
        except StopIteration:
            pass

        result = old_function(*processed_args, **processed_kwargs)

        close_context()
        
        return result
    
    @wraps(old_function)
    async def new_async_function(*args, **kwargs):
        processed_args:     list[Any] = []
        processed_kwargs:   dict[str, Any] = {}
        
        args, kwargs = update_kwargs_with_defaults(args, kwargs)

        generator = process_args_kwargs(args, kwargs, processed_args, processed_kwargs)

        try:
            while True:
                to_process = next(generator)

                generator.send(await process_depends_async(to_process))
        except StopIteration:
            pass
        
        result = await old_function(*processed_args, **processed_kwargs)

        await close_context_async()

        return result

    if iscoroutinefunction(old_function):
        return new_async_function

    return new_function
