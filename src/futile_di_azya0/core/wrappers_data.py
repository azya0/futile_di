from typing import Generator, AsyncGenerator, Any


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


class WrapperData:
    def __init__(self):
        self.__context_holder:    ContextHolder = ContextHolder()
        self.__processed_args:    list[Any] = []
        self.__processed_kwargs:  dict[str, Any] = {}

    def get_context(self) -> ContextHolder:
        return self.__context_holder
    
    def get_params(self) -> tuple[list[Any], dict[str, Any]]:
        return self.__processed_args, self.__processed_kwargs
    
    def close_context(self):
        self.__context_holder.close_sync()
    
    async def close_context_async(self):
        await self.__context_holder.close_async()
