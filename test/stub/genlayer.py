"""Local GenLayer stub. Enough surface to run contracts/retainer.py offline.

Copied from suborn/test/stub/genlayer.py @ 9c7b0af, with u32
added from the Jastrow harness. Same approach as both: this is not a simulator of consensus.
It is a way to exercise the state machine, the money, and the dedup without
waiting on Bradbury. Consensus behaviour is faked by a scripted model that the
tests drive on purpose.
"""

from dataclasses import dataclass as _dataclass
import typing

__all__ = [
    "gl",
    "Address",
    "TreeMap",
    "DynArray",
    "u32",
    "u256",
    "bigint",
    "allow_storage",
]


def allow_storage(cls):
    return cls


def u32(v):
    v = int(v)
    if v < 0 or v > 0xFFFFFFFF:
        raise OverflowError("u32 out of range")
    return v


def u256(v):
    v = int(v)
    if v < 0:
        raise OverflowError("u256 underflow")
    return v


bigint = int


class Address:
    def __init__(self, value):
        if isinstance(value, Address):
            value = value._v
        self._v = str(value).lower()

    @property
    def as_hex(self):
        return self._v

    def __eq__(self, other):
        return isinstance(other, Address) and other._v == self._v

    def __hash__(self):
        return hash(self._v)

    def __repr__(self):
        return "Address(%s)" % self._v


class TreeMap(dict):
    """Auto-defaulting map, mirroring typed storage slots."""

    def __init__(self, factory=None):
        super().__init__()
        self._factory = factory

    def __missing__(self, key):
        if self._factory is None:
            return 0
        value = self._factory()
        self[key] = value
        return value


class DynArray(list):
    pass





class _UserError(Exception):
    pass


class _Vm:
    UserError = _UserError


class _Message:
    def __init__(self):
        self.sender_address = Address("0x" + "00" * 20)
        self.value = 0


class _Nondet:
    def __init__(self):
        self.handler = None
        self.calls = []

    def exec_prompt(self, prompt, response_format=None):
        self.calls.append(prompt)
        if self.handler is None:
            raise RuntimeError("no model handler installed in the stub")
        return self.handler(prompt)

    class _Web:
        def render(self, url, mode="text"):
            raise RuntimeError("live fetch is not used in retainer/1")

    web = _Web()


class _EqPrinciple:
    @staticmethod
    def prompt_comparative(fn, principle):
        return fn()

    @staticmethod
    def prompt_non_comparative(fn, task=None, criteria=None):
        return fn()

    @staticmethod
    def strict_eq(fn):
        return fn()


class _Advanced:
    def __init__(self):
        self.transfers = []

    def emit_transfer(self, to, amount):
        self.transfers.append((to, int(amount)))


class _PublicWrite:
    def __call__(self, fn):
        fn._gl_public = "write"
        return fn

    def payable(self, fn):
        fn._gl_public = "write.payable"
        return fn


class _Public:
    write = _PublicWrite()

    @staticmethod
    def view(fn):
        fn._gl_public = "view"
        return fn


class _StorageMeta(type):
    """Instantiate declared storage slots from their annotations."""

    def __call__(cls, *args, **kwargs):
        obj = cls.__new__(cls)
        for klass in reversed(cls.__mro__):
            for name, ann in getattr(klass, "__annotations__", {}).items():
                origin = typing.get_origin(ann) or ann
                if origin is TreeMap:
                    inner = typing.get_args(ann)[1] if typing.get_args(ann) else None
                    inner_origin = typing.get_origin(inner) or inner
                    if inner_origin in (TreeMap, DynArray):
                        setattr(obj, name, TreeMap(lambda o=inner_origin: o()))
                    else:
                        setattr(obj, name, TreeMap())
                elif origin is DynArray:
                    setattr(obj, name, DynArray())
        obj.__init__(*args, **kwargs)
        return obj


class Contract(metaclass=_StorageMeta):
    pass


class _Gl:
    Contract = Contract
    vm = _Vm()
    public = _Public()
    eq_principle = _EqPrinciple()

    def __init__(self):
        self.message = _Message()
        self.nondet = _Nondet()
        self.advanced = _Advanced()


gl = _Gl()
gl.contract = type("contract", (), {"Contract": Contract})
