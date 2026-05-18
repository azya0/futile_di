import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator, Generator

from aioresponses import aioresponses 
from aiohttp import ClientSession, ClientResponse, ClientError
import pytest

from src.futile_di_azya0 import Depends, inject


@dataclass(frozen=True, eq=True)
class User:
    id:     int
    name:   str


@pytest.fixture(scope="function")
def mock_generator() -> Generator[aioresponses]:
    with aioresponses() as mock:
        mock.get(
            "https://api.example.com/users/1",
            payload={"id": 1, "name": "John"},
            status=200
        )
        
        mock.post(
            "https://api.example.com/users/2",
            payload={"id": 2, "name": "Jane"},
            status=201
        )
        
        mock.get(
            "https://api.example.com/users/999",
            status=404,
            exception=ClientError("Not found")
        )

        yield mock


async def get_session() -> AsyncGenerator[ClientSession]:
    async with ClientSession() as session:
        yield session


@pytest.mark.usefixtures("mock_generator")
def test_get_user_1():
    async def get_first_user(session: ClientSession = Depends(get_session)) -> AsyncGenerator[User]:
        async with session.get("https://api.example.com/users/1") as response:
            data = await response.json()

            yield User(**data)
    
    @inject
    async def enpoint_example(first_user: User = Depends(get_first_user)) -> User:
        return first_user
    
    assert asyncio.run(enpoint_example()) == User(1, "John")


def self_mock_generator() -> Generator[aioresponses]:
    with aioresponses() as mock:
        mock.get(
            "https://api.example.com/status",
            payload={"status": True},
            status=200
        )

        yield mock

@inject
def test_get_status_self_injection(mock: aioresponses = Depends(self_mock_generator)):
    async def get_status(session: ClientSession = Depends(get_session)) -> AsyncGenerator[ClientResponse]:
        async with session.get("https://api.example.com/status") as response:
            yield response
    
    @inject
    async def enpoint_example(response: ClientResponse = Depends(get_status)) -> bool:
        await asyncio.sleep(0.01)
        
        return (await response.json())["status"]
    
    assert asyncio.run(enpoint_example())


@pytest.mark.usefixtures("mock_generator")
def test_get_user_2():
    async def get_second_user(session: ClientSession = Depends(get_session)) -> AsyncGenerator[User]:
        async with session.post("https://api.example.com/users/2") as response:
            data = await response.json()

            yield User(**data)
    
    @inject
    async def enpoint_example(first_user: User = Depends(get_second_user)) -> User:
        return first_user
    
    assert asyncio.run(enpoint_example()) == User(2, "Jane")


@pytest.mark.usefixtures("mock_generator")
def test_get_missed_user():
    async def get_999_user(session: ClientSession = Depends(get_session)) -> AsyncGenerator[ClientResponse]:
        async with session.get("https://api.example.com/users/999") as response:
            yield response
    
    @inject
    async def enpoint_example(first_user: ClientResponse = Depends(get_999_user)) -> User:
        return User(**(await first_user.json()))
    
    try:
        asyncio.run(enpoint_example())
    except ClientError as error:
        assert str(error) == "Not found"
