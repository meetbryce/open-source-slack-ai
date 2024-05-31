def test_package_import():
    """Test the import of the package."""
    try:
        import ossai
    except ImportError:
        assert False, "Failed to import the package."
