class DependsAsyncError(ValueError):
    def __init__(self):
        super().__init__("can't process async depends in sync wrapped function")


class SyncContextResultError(ValueError):
    def __init__(self):
        super().__init__("trying to get context from SyncContextResult with state SyncContextState.NO_CONTEXT")


class AsyncContextResultError(ValueError):
    def __init__(self):
        super().__init__("trying to get context from AsyncContextResult with state AsyncContextState.NO_CONTEXT")
