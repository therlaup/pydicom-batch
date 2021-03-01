import logging

def setup_logging(app_name):
    """Return the application logger.
    Parameters
    ----------
    app_name : str
        The name of the application.
    Returns
    -------
    logger : logging.Logger, optional
        The logger to use for logging.
    """
    formatter = logging.Formatter('%(levelname).1s: %(message)s')

    # Setup pynetdicom library's logging
    pynd_logger = logging.getLogger('pynetdicom')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    pynd_logger.addHandler(handler)
    pynd_logger.setLevel(logging.ERROR)

    # Setup application's logging
    app_logger = logging.Logger(app_name)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.ERROR)
    pynd_logger.setLevel(logging.ERROR)

    return app_logger