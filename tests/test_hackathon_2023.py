def test_package_import():
    """Test the import of the package."""
    try:
        import hackathon_2023
    except ImportError:
        assert False, "Failed to import the package."
