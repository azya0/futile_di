from ..depends import Depends


class DependsAsyncError(ValueError):
    def __init__(self):
        super().__init__("can't process async depends in sync wrapped function")


class SyncContextResultError(ValueError):
    def __init__(self):
        super().__init__("trying to get context from SyncContextResult with state SyncContextState.NO_CONTEXT")


class AsyncContextResultError(ValueError):
    def __init__(self):
        super().__init__("trying to get context from AsyncContextResult with state AsyncContextState.NO_CONTEXT")


class DependsValueWrappeUnprocessedError(ValueError):
    def __init__(self):
        super().__init__("trying to get depends until it was processed")


class DependsValueWrappeNoNameError(BaseException):
    def __init__(self, depends: Depends):
        super().__init__(f"depends {depends} is not other depends kwarg, but trying to process as")
