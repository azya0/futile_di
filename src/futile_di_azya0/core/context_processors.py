from typing import Generator, Any

from .depends import Depends
from .depends_processors import (
    process_depends, SyncContextState,
    process_depends_async, AsyncContextState
)
from .wrappers_data import ContextHolder


async def process_async_context(depends: Depends, depends_generator: Generator[Depends, Any, None], context_holder: ContextHolder):
    while True:
        contexts, value = await process_depends_async(depends)

        for context in contexts:
            context_state = context.get_state()

            if context_state != AsyncContextState.NO_CONTEXT:
                generator = context.get_generator()

                if context_state == AsyncContextState.GENERATOR:
                    context_holder.add_sync_context(generator)
                else:
                    context_holder.add_async_context(generator)

        try:
            depends = depends_generator.send(value)
        except StopIteration:
            break


def process_sync_context(depends: Depends, depends_generator: Generator[Depends, Any, None], context_holder: ContextHolder):
    while True:
        contexts, value = process_depends(depends)

        for context in contexts:
            if context.get_state() == SyncContextState.GENERATOR:
                context_holder.add_sync_context(context.get_generator())
        
        try:
            depends = depends_generator.send(value)
        except StopIteration:
            break
