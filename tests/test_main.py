import asyncio
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from functools import lru_cache
from typing import AsyncGenerator, Generator

from src.futile_di_azya0 import Depends, inject, DependsAsyncError


def test_no_depends():
    @inject
    def some_function(a: int = Depends(4)) -> int:
        return a + 1
    
    assert some_function() == 5


def test_args_and_kwargs_no_depends():
    @inject
    def some_function(a: int, b: int = 4) -> int:
        return a + b
    
    assert some_function(4) == 8
    assert some_function(5) == 9
    assert some_function(a=3, b=5) == 8
    assert some_function(3, b=5) == 8


def example_depends() -> Generator[int]:
    yield 1


def test_generator_depends():
    @inject
    def some_function(arg: int = Depends(example_depends)) -> int:
        return arg + 1
    
    assert some_function() == 2


class GeneratorWithContext:
    def __init__(self):
        self.is_open: bool = True
    
    def get_generator(self) -> Generator[int]:
        yield 1

        self.is_open = False


def test_generator_context():
    context = GeneratorWithContext()

    @inject
    def some_function(arg: int = Depends(context.get_generator)) -> int:
        assert context.is_open
        
        result = arg + 1

        assert context.is_open

        return result
    
    assert some_function() == 2
    assert not context.is_open


def test_async_function_depends():
    async def hype() -> int:
        await asyncio.sleep(0.01)

        return 1

    @inject
    async def some_function(arg: int = Depends(hype)):
        return arg + 1

    assert asyncio.run(some_function()) == 2
    assert asyncio.run(some_function(4)) == 5


class AsyncGeneratorWithContext:
    def __init__(self):
        self.is_open: bool = True
    
    async def get_generator(self) -> AsyncGenerator[int]:
        await asyncio.sleep(0.01)
        
        yield 1

        self.is_open = False


def test_async_generator_context():
    context = AsyncGeneratorWithContext()

    @inject
    async def some_function(arg: int = Depends(context.get_generator)) -> int:
        assert context.is_open
        
        result = arg + 1

        assert context.is_open

        return result
    
    assert asyncio.run(some_function()) == 2
    assert not context.is_open


def test_not_async_error():
    context = AsyncGeneratorWithContext()

    @inject
    def some_function(arg: int = Depends(context.get_generator)) -> int:
        assert context.is_open
        
        result = arg + 1

        assert context.is_open

        return result
    
    try:
        asyncio.run(some_function())
    except DependsAsyncError:
        pass


def test_sync_generator_in_async_func():
    context = GeneratorWithContext()

    @inject
    async def some_function(arg: int = Depends(context.get_generator)) -> int:
        await asyncio.sleep(0.01)
        
        assert context.is_open
        
        result = arg + 1

        assert context.is_open

        return result
    
    assert asyncio.run(some_function()) == 2


def test_nested_depends():
    def one_generator() -> Generator[int]:
        yield 1
    
    class SomeClass:
        def __init__(self, value: int):
            self.value = value
        
        def get(self) -> int:
            return self.value

    def get_instance(value: int = Depends(one_generator)) -> SomeClass:
        return SomeClass(value)

    @inject
    def some_function(arg: SomeClass = Depends(get_instance)) -> int:
        return arg.get() + 1
    
    assert some_function() == 2


def test_nested_depends_context():
    class Context(AbstractContextManager):
        def __init__(self):
            super().__init__()

            self.is_open = False
        
        def __enter__(self) -> AbstractContextManager:
            self.is_open = True

            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self.is_open = False

            return super().__exit__(exc_type, exc_value, traceback)


    context = Context()

    
    def one_generator() -> Generator[int]:
        assert not context.is_open
        
        with context:
            assert context.is_open

            yield 1
    
    class SomeClass:
        def __init__(self, value: int):
            self.value = value
        
        def get(self) -> int:
            return self.value

    def get_instance(value: int = Depends(one_generator)) -> SomeClass:
        assert context.is_open
        
        return SomeClass(value)

    @inject
    def some_function(arg: SomeClass = Depends(get_instance)) -> int:
        assert context.is_open
        
        return arg.get() + 1
    
    assert some_function() == 2
    assert not context.is_open


def test_context_exception():
    def some_dep_function(a: int, x: int = Depends(2)) -> int:
        return a + x
    
    @inject
    def some_function(a: int, y: int = Depends(some_dep_function)) -> int:
        return a + y
    
    try:
        some_function()
    except TypeError as error:
        assert str(error) == "test_context_exception.<locals>.some_dep_function() missing 1 required positional argument: 'a'"


def test_context_lambda():
    def some_dep_function(a: int, x: int = Depends(2)) -> int:
        return a + x
    
    @inject
    def some_function(a: int, y: int = Depends(lambda x=Depends(4) : some_dep_function(a=4, x=x))) -> int:
        return a + y
    
    assert some_function(4) == 12


def test_nested_async_depends_context():
    class Context(AbstractAsyncContextManager):
        def __init__(self):
            super().__init__()

            self.is_open = False
        
        async def __aenter__(self) -> AbstractContextManager:
            await asyncio.sleep(0.01)
            
            self.is_open = True

            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            await asyncio.sleep(0.01)

            self.is_open = False

            return await super().__aexit__(exc_type, exc_value, traceback)


    context = Context()
    
    async def one_generator() -> AsyncGenerator[int]:
        assert not context.is_open
        
        async with context:
            assert context.is_open

            await asyncio.sleep(0.01)

            yield 1
    
    class SomeClass:
        def __init__(self, value: int):
            self.value = value
        
        def get(self) -> int:
            return self.value

    async def get_instance(value: int = Depends(one_generator)) -> SomeClass:
        assert context.is_open

        await asyncio.sleep(0.01)
        
        return SomeClass(value)

    @inject
    async def some_function(arg: SomeClass = Depends(get_instance)) -> int:
        await asyncio.sleep(0.01)

        assert context.is_open
        
        return arg.get() + 1
    
    assert asyncio.run(some_function()) == 2
    assert not context.is_open


def test_nested_async_with_sync_depends_context():
    class Context(AbstractAsyncContextManager):
        def __init__(self):
            super().__init__()

            self.is_open = False
        
        async def __aenter__(self) -> AbstractContextManager:
            await asyncio.sleep(0.01)
            
            self.is_open = True

            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            await asyncio.sleep(0.01)

            self.is_open = False

            return await super().__aexit__(exc_type, exc_value, traceback)


    context = Context()
    
    async def one_generator() -> AsyncGenerator[int]:
        assert not context.is_open
        
        async with context:
            assert context.is_open

            await asyncio.sleep(0.01)

            yield 1
    
    class SomeClass:
        def __init__(self, value: int):
            self.value = value
        
        def get(self) -> int:
            return self.value

    def get_instance(value: int = Depends(one_generator)) -> SomeClass:
        assert context.is_open
        
        return SomeClass(value)

    @inject
    async def some_function(arg: SomeClass = Depends(get_instance)) -> int:
        await asyncio.sleep(0.01)

        assert context.is_open
        
        return arg.get() + 1
    
    assert asyncio.run(some_function()) == 2
    assert not context.is_open


def test_nested_async_with_sync_huge_depends_context():
    class Context(AbstractAsyncContextManager):
        def __init__(self):
            super().__init__()

            self.is_open = False
        
        async def __aenter__(self) -> AbstractContextManager:
            await asyncio.sleep(0.01)
            
            self.is_open = True

            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            await asyncio.sleep(0.01)

            self.is_open = False

            return await super().__aexit__(exc_type, exc_value, traceback)


    context = Context()
    
    async def one_generator() -> AsyncGenerator[int]:
        assert not context.is_open
        
        async with context:
            assert context.is_open

            await asyncio.sleep(0.01)

            yield 1
    
    class SomeClass:
        def __init__(self, value: int):
            self.value = value
        
        def get(self) -> int:
            return self.value

    def get_instance(value: int = Depends(one_generator)) -> SomeClass:
        assert context.is_open
        
        return SomeClass(value)

    def get_arg2() -> Generator[int]:
        yield 28

    async def get(get_arg2_deps: int = Depends(get_arg2)) -> int:
        await asyncio.sleep(0.02)

        return get_arg2_deps + 1

    @inject
    async def some_function(arg1: SomeClass = Depends(get_instance), arg2: int = Depends(get)) -> int:
        await asyncio.sleep(0.01)

        assert context.is_open
        
        return arg1.get() + arg2
    
    assert asyncio.run(some_function()) == 30
    assert not context.is_open


def test_multiple_depends():
    def one_generator() -> Generator[int]:
        yield 1
    
    @inject
    def some_function(a: int = Depends(one_generator), b: int = Depends(one_generator), c: int = Depends(one_generator)) -> int:
        return a + b + c
    
    assert some_function() == 3


def test_multiple_nested_depends():
    def one_generator() -> Generator[int]:
        yield 1
    
    def multiple_function(a: int = Depends(one_generator), b: int = Depends(one_generator), c: int = Depends(one_generator)) -> int:
        return a + b + c
    
    @inject
    def some_function(a: int = Depends(one_generator), b: int = Depends(multiple_function), c: int = Depends(5)):
        return a + b + c
    
    assert some_function() == 9


def test_semiasync_exception():
    async def one_generator() -> AsyncGenerator[int]:
        await asyncio.sleep(0.01)

        yield 1
    
    def multiple_function(a: int = Depends(one_generator), b: int = Depends(one_generator), c: int = Depends(one_generator)) -> int:
        return a + b + c
    
    @inject
    def some_function(a: int = Depends(one_generator), b: int = Depends(multiple_function), c: int = Depends(5)):
        return a + b + c
    
    try:
        some_function()
    except DependsAsyncError:
        pass


def test_multiple_nested_depends_semiasync():
    async def one_generator() -> AsyncGenerator[int]:
        await asyncio.sleep(0.01)
        
        yield 1
    
    def multiple_function(a: int = Depends(one_generator), b: int = Depends(one_generator), c: int = Depends(one_generator)) -> int:
        return a + b + c
    
    @inject
    async def some_function(a: int = Depends(one_generator), b: int = Depends(multiple_function), c: int = Depends(5)) -> int:
        return a + b + c
    
    assert asyncio.run(some_function()) == 9


def test_singleton():
    @lru_cache
    def singleton_generator() -> Generator[int]:
        counter = 0

        while True:
            counter += 1

            yield counter
    
    @inject
    def some_function(a: int = Depends(singleton_generator), b: int = Depends(singleton_generator), c: int = Depends(singleton_generator)) -> int:
        return a + b + c
    
    assert some_function() == 6


def test_multiple_decorators():
    def some_decorator(old_function):
        def new_function():
            return old_function() + 1
        return new_function
    
    @some_decorator
    @some_decorator
    def one_function():
        return 2
    
    @inject
    def some_function(a: int = Depends(one_function)):
        return a + 1
    
    assert some_function() == 5


def test_multiple_decorators_on_generator():
    def do_nothing(old_function):
        return old_function
    
    @do_nothing
    @do_nothing
    @do_nothing
    def some_generator() -> Generator[float]:
        yield 1.1
    
    @inject
    def some_function(a: int = Depends(some_generator)) -> float:
        return a + 2.2
    
    assert some_function() == 1.1 + 2.2
