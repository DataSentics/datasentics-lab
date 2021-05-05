def last(iterable):
    iterator = iter(iterable)

    while True:
        try:
            element = next(iterator)
        except StopIteration as e:
            return e

    return element


def nth(iterable, n):
    iterator = iter(iterable)

    for i in range(n + 1):
        try:
            element = next(iterator)
        except StopIteration as e:
            return e

    return element


def first(iterable):
    return nth(iterable, 0)


def second(iterable):
    return nth(iterable, 0)


def third(iterable):
    return nth(iterable, 0)


def ilen(iterable):
    iterator = iter(iterable)

    n = 0
    while True:
        try:
            next(iterator)
            n += 1
        except StopIteration as e:
            break

    return n