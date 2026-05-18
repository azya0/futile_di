# futile_di

```shell
pip install futile-di-azya0
```

## Описание

**futile_di** - маленькая библиотека для **инъекции зависимостей**, не привязанной к реализации конкретного фреймворка (вроде Depends из FastAPI). 

Допустим у нас есть генератор для контроля цикла жизни сессии:

```python
def get_session():
    with create_session() as session:
        yield session
```

Тогда, чтобы получить сессию нам нужно:

* Создавать сильную зависимость  

**Или**

* Хранить созданный генератор на стеке функции-консьюмера
* Вручную вызывать ```next(...)``` для получения сессии

```python
def get_user(generator=get_session()):
    session = next(generator)

    ...
```

Вместо этого можно использовать механизм инъекции зависимости, который будет делать это "под капотом":

```python
from futile_di_azya0 import Depends, inject


def get_session() -> Session:
    with create_session() as session:
        yield session

@inject
def get_user(session: Session = Depends(get_session)):
    ...
```

На данный момент ```@inject``` и ```Depends``` поддерживают:
* синхронные функции
* асинхронные функции
* генераторы
* асинхронные генераторы

## Реализация

```inject``` - декоратор для синхронной/асинхронной функции. Он ищет класс ```Depends``` (*main*) как среди параметров функции по умолчанию, так и среди переданных значений. Далее для каждого *main* он собирает стек вложенных ```Depends```, чтобы получить значение для текущего (*main*), параллельно сохраняя контекст до конца выполнения функции:

*При анализе вложенных main ```Depends``` ищутся только среди параметров по умолчанию*

Поддерживаемые типы для обёртки в ```Depends```:

```python
class DependsType(Enum):
    VALUE = 0,
    SYNC = 1,
    ASYNC = 2,
    GENERATOR = 3,
    ASYNC_GENERATOR = 4,
```

Если это ```VALUE```, то он просто возвращает значение. Если это ```SYNC``` или ```ASYNC```, то он вызывает их, получает значение и возвращает его. Если это ```GENERATOR``` или ```ASYNC_GENERATOR```, то он получает первое значение, сохраняет генераторы до конца выполнения функции, а потом вызывает ещё один ```next(...)/await anext(...)```, для того, чтобы генератор мог завершить свой контекст. При этом, если исключение ```StopIteration/StopAsyncIteration``` не было получено, то исключения не будет.

**В конечном итоге генераторы удаляются, чтобы контекст мог закрыться**

## Пример


```python
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
```

Допустим, у нас есть некоторый контекст асинхронный ```Context```. Мы хотим, чтобы:

* Зависимость с этим контекстом имела некоторую глубину вложенности
* Контекст сохранялся до конца выполнения функции, которую мы обернули в ```@inject```
* Асинхронные зависимости могли зависеть от синхронных и наоборот

Этот код был взят из теста к библиотеке. Он показывает работоспособность всех вышеперечисленных запросов.


## Тесты

Для **futile_di** было написано несколько тестов. Запустить их можно через библиотеку ```pytest``` из корневой директории командой:

```shell
pytest -s 
```
