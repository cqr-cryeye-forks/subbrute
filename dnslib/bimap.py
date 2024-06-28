# -*- coding: utf-8 -*-

"""
    Bimap - bidirectional mapping between code/value
"""

from typing import Type, Dict, Any


class BimapError(Exception):
    pass


class Bimap(object):
    """
        Bi-directional mapping between code/text.

        Initialised using:

            name:   Used for exceptions
            dict:   Dict mapping from code (numeric) to text
            error:  Error type to raise if key not found

        The class provides:

            * A 'forward' map (code->text) which is accessed through
              __getitem__ (bimap[code])
            * A 'reverse' map (code>value) which is accessed through
              __getattr__ (bimap.text)
            * A 'get' method which does a forward lookup (code->text)
              and returns a textual version of code if there is no
              explicit mapping (or default provided)

        >>> class TestError(Exception):
        ...     pass

        >>> TEST = Bimap('TEST',{1:'A', 2:'B', 3:'C'},TestError)
        >>> TEST[1]
        'A'
        >>> TEST.A
        1
        >>> TEST.X
        Traceback (most recent call last):
        ...
        TestError: TEST: Invalid reverse lookup: [X]
        >>> TEST[99]
        Traceback (most recent call last):
        ...
        TestError: TEST: Invalid forward lookup: [99]
        >>> TEST.get(99)
        '99'

    """

    def __init__(self, name: str, forward: Dict[int, str], error: Type[Exception] = KeyError):
        self.name = name
        self.error = error
        self.forward = forward.copy()
        self.reverse = {v: k for k, v in forward.items()}

    def get(self, k: int, default: Any = None) -> str:
        return self.forward.get(k, default or str(k))

    def __getitem__(self, k: int) -> str:
        try:
            return self.forward[k]
        except KeyError:
            raise self.error("%s: Invalid forward lookup: [%s]" % (self.name, k))

    def __getattr__(self, k: str) -> int:
        try:
            return self.reverse[k]
        except KeyError:
            raise self.error("%s: Invalid reverse lookup: [%s]" % (self.name, k))


if __name__ == '__main__':
    import doctest

    doctest.testmod()
