import asyncio
from typing import AsyncGenerator, Generator

from futile_di import Depends, inject, DependsAsyncError


def test_no_depends():
    @inject
    def some_function(a: int = Depends(4)) -> int:
        return a + 1
    
    assert some_function() == 5


def test_args_and_kwargs():
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


def test_async_function():
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

    @inject
    def get_instance(value: int = Depends(one_generator)) -> SomeClass:
        return SomeClass(value)

    @inject
    def some_function(arg: SomeClass = Depends(get_instance)) -> int:
        return arg.get() + 1
    
    assert some_function() == 2
