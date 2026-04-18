def test_import_app():
    import webapp.app
    assert True


def test_config_loader():
    from scripts.config_loader import get_config
    cfg = get_config()
    assert cfg is not None
