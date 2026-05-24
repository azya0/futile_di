from functools import wraps
from inspect import iscoroutinefunction, signature
from typing import Any

from .wrappers_data import WrapperData
from .context_processors import process_sync_context, process_async_context
from .wrappers_processpr import main_new_function, NewFuncState


def inject(old_function):
    old_function_sig = signature(old_function)

    def update_kwargs_with_defaults(args, kwargs) -> tuple[tuple[Any], dict[str, Any]]:
        bound = old_function_sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        
        return bound.args, bound.kwargs

    @wraps(old_function)
    def new_function(*args, **kwargs):
        depends_generator = main_new_function(update_kwargs_with_defaults(args, kwargs))

        while (generator_step := next(depends_generator)):
            status, params = generator_step

            if (status == NewFuncState.PROCESS_DATA):
                process_sync_context(*params)
                continue

            params: tuple[WrapperData, tuple[list[Any], dict[str, Any]]]
            
            wrapper_data, (new_args, new_kwargs) = params
            
            result = old_function(*new_args, **new_kwargs)

            wrapper_data.close_context()

            return result
    
    @wraps(old_function)
    async def new_async_function(*args, **kwargs):
        depends_generator = main_new_function(update_kwargs_with_defaults(args, kwargs))

        while True:
            try:
                status, params = next(depends_generator)
            except StopIteration as result:
                return await result.value

            if (status == NewFuncState.PROCESS_DATA):
                await process_async_context(*params)
                continue

            params: tuple[WrapperData, tuple[list[Any], dict[str, Any]]]
            
            wrapper_data, (new_args, new_kwargs) = params
            
            result = await old_function(*new_args, **new_kwargs)

            await wrapper_data.close_context_async()

            return result

    if iscoroutinefunction(old_function):
        return new_async_function

    return new_function
