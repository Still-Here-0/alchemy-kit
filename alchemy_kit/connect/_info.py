from typing import Optional
import sqlalchemy
import random
import string


class ConnectionInfo:

    def __init__(self, conn_url: sqlalchemy.URL, unique_id: Optional[str]) -> None:
        self.conn_url = conn_url

        if isinstance(unique_id, str):
            self.unique_id = unique_id
        else:
            self.unique_id = ''.join(random.choices(string.ascii_letters + string.digits, k=32))

