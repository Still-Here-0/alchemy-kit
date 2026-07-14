class NotInstantiable:
    def __new__(cls, *_args, **_kwargs):
        raise TypeError(f"{cls.__name__} is a global namespace and cannot be instantiated.")

class Settings(NotInstantiable):
    """Global, mutable configuration. Not instantiable — use the class directly.

    Example:
    ```
        from alchemy_kit.resources import Settings

        Settings.replacement_markers.append('?')   # in-place change
        Settings.replacement_markers = ['!', '?']  # or reassign
    ```
    """

    replacement_markers: list[str] = ['!']
    project_markers: list[str] = ['pyproject.toml', 'setup.py', 'setup.cfg', '.git']

    class FileExtraction(NotInstantiable):
        """Keys read from connection config sources (JSON entries, ``.env`` files).

        Each ``*_marker`` is the lookup key used when parsing a connection
        definition into a ``ConnectionInfo``. Override a marker to match the
        naming used in your own config files. Not instantiable — use the class
        directly.

        Example:
        ```
            from alchemy_kit.resources import Settings

            Settings.FileExtraction.server_marker = 'host'  # read 'host' instead of 'server'
        ```
        """

        dialect_marker = "dialect"
        unique_id_marker = "unique_id"
        auth_marker = "auth"
        driver_marker = "driver"
        api_marker = "api"
        server_marker = "server"
        database_marker = "database"
        user_name_marker = "user_name"
        user_pwd_marker = "user_pwd"
        encrypt_marker = "encrypt"
        trust_server_certificate_marker = "trust_server_certificate"

