import innkeeper
import innkeeper_core


def test_packages_import():
    assert innkeeper_core.__doc__
    assert innkeeper.__doc__
