import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

import sqlalchemy

from ..types.generic_path import GenericPath
from ._settings import Settings
from ..types._sql_parameters import SqlParamters, SqlTextReplacement


@dataclass(kw_only=True)
class SQL:
    sql_path: GenericPath | None                        = None
    raw_query: str | None                               = None
    script_dir: Path | None                             = field(default=None, init=False)
    processed_query: str | None                         = field(default=None, init=False, repr=False)
    query_parameters: SqlParamters                      = field(default_factory=dict)
    text_replacements: SqlTextReplacement               = field(default_factory=dict)
    f_check: Callable[[sqlalchemy.Connection], bool]    = field(default=lambda _: True)

    def __post_init__(self) -> None:
        if (self.sql_path is None) == (self.raw_query is None):
            raise ValueError("Provide exactly one of 'sql_path' or 'raw_query', not both or neither.")

    def set_script_dir(self, script_dir: Path):
        self.script_dir = script_dir

    def process_query(self):
        if self.sql_path is not None:
            self.sql_path = self._parse_sql_path(self.sql_path)
            self.raw_query = self.sql_path.read_text("UTF-8")

        assert isinstance(self.raw_query, str), "If you get this assertion error this is a bug, 'self.raw_query' is None on 'SQL.process_query'"
        converted_query = self._convert_parameters(self.raw_query)
        self.processed_query = self._replace_texts(converted_query)

    def _parse_sql_path(self, sql_path: GenericPath) -> Path:
        if self.script_dir is None or not self.script_dir.exists():
            raise ValueError(f"Script dir do not exits: {self.script_dir}")

        parsed_sql_path = Path(sql_path).with_suffix(".sql")

        full_file_path = self.script_dir / parsed_sql_path
        if not full_file_path.exists():
            raise ValueError(f"Path do not exists: {full_file_path}")

        return full_file_path.resolve()

    def _convert_parameters(self, query: str) -> str:
        if "@" not in query:
            return query

        parameters: list[str]
        if isinstance(self.query_parameters, Sequence):
            parameters = list(self.query_parameters[0].keys())
        else:
            parameters = list(self.query_parameters.keys())

        for param in parameters:
            pattern = rf"@{re.escape(param)}\b"
            replace = f":{param}"
            query = re.sub(pattern, replace, query)

        return query

    def _replace_texts(self, query: str) -> str:
        for key, value in self.text_replacements.items():
            for marker in Settings.replacement_markers:
                pattern = f"{marker}{re.escape(key)}{marker}"
                query = re.sub(pattern, value, query)

        return query

