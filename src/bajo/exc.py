class BajoError(Exception):
    pass


class MissingDefError(BajoError):
    pass


class DuplicateDefError(BajoError):
    pass


class DetachedLabelError(BajoError):
    pass


class BuildError(BajoError):
    pass


class AddrError(BajoError):
    pass


class CycleError(BajoError):
    pass


class DirectiveError(BajoError):
    pass
