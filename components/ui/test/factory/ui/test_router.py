from factory.ui.runtime.router import Router


def test_resolve_explicit_route():
    router = Router(routes={"/": "dashboard", "/profile": "user_profile"})
    assert router.resolve("/") == "dashboard"
    assert router.resolve("/profile") == "user_profile"


def test_resolve_implicit_route():
    router = Router()
    assert router.resolve("/login") == "login"
    assert router.resolve("/settings/security") == "settings/security"


def test_resolve_root_default():
    router = Router()
    assert router.resolve("/") == "index"
