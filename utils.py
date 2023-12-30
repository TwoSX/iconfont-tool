from threading import Timer


class SetTimeOut:
    _timer = Timer

    def __init__(self, fn, delay, args=None, kwargs=None) -> None:
        self._timer = Timer(delay, fn, args, kwargs)
        self._timer.start()

    def clear(self):
        self._timer.cancel()

    def is_finished(self):
        return self._timer.finished.is_set()


class Debounce:  # 防抖
    timer: SetTimeOut = None

    def __init__(self, func, delay) -> None:
        self.func = func
        self.delay = delay

    def __call__(self, *args, **kwargs):
        if self.timer is not None:
            self.timer.clear()
        self.timer = SetTimeOut(self.func, self.delay, args, kwargs)


class Throttle:  # 节流
    timer: SetTimeOut = None

    def __init__(self, func, delay) -> None:
        self.func = func
        self.delay = delay

    def __call__(self, *args, **kwargs):
        if (self.timer is None) or self.timer.is_finished():
            self.timer = SetTimeOut(self.func, self.delay, args, kwargs)
