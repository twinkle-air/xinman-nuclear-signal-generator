import launcher


def test_launcher_uses_package_entrypoint() -> None:
    assert callable(launcher.main)

