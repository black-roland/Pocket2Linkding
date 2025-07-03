# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "attrs",
#   "unidecode",
# ]
# ///
"""
Migrate Mozilla Pocket to linkding.

This uses the Pocket export format as input and creates .html bookmark files that can
be directly imported into linkding.  Will preserve the date the link was added to
Pocket and any Pocket tags.

See https://github.com/hkclark/Pocket2Linkding for more information.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
from typing import Iterator

import attrs
from unidecode import unidecode


@attrs.frozen
class Config:
    """Configuration via cmd-line args."""

    _parser: argparse.ArgumentParser = attrs.field(
        init=False,
        validator=attrs.validators.instance_of(argparse.ArgumentParser),
    )
    """The parser."""

    @_parser.default
    def _parser_default(self):
        """Build the _parser attribute."""
        parser = argparse.ArgumentParser(
            description="Migrate from Mozilla Pocket to Linkding"
        )
        parser.add_argument(
            "--pocket_export_dir",
            "-d",
            help="Directory containing .csv file(s) exported from Pocket",
            type=str,
            required=True,
        )
        return parser

    _parsed_args: argparse.Namespace = attrs.field(
        init=False,
        default=attrs.Factory(
            takes_self=True,
            factory=lambda self: self._parser.parse_args(),
        ),
        validator=attrs.validators.instance_of(argparse.Namespace),
    )
    """Results of argparse.parse_args()."""

    pocket_export_path: Path = attrs.field(
        init=False,
        default=attrs.Factory(
            takes_self=True,
            factory=lambda self: Path(self._parsed_args.pocket_export_dir),
        ),
    )
    """Pocket Export Dir as a ready-to-use pathlib Path obj."""

    @pocket_export_path.validator
    def _pocket_export_path_validator(self, attrib, value):
        """Make sure the Pocket Export Dir looks right."""
        if not value.exists():
            raise ValueError(f"Invalid pocket-export-dir: '{value}'")
        if not value.is_dir():
            raise ValueError(f"pocket-export-dir must be a directory: '{value}'")


@attrs.frozen
class BookmarkFile:
    """A bookmark HTML file in the format used by Linkding."""

    header: str = attrs.field(
        init=False,
        default=(
            "<!DOCTYPE NETSCAPE-Bookmark-file-1>\n"
            '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">\n'
            "<TITLE>Bookmarks</TITLE>\n\n<H1>Bookmarks</H1>\n\n<DL><p>\n\n"
        ),
        validator=attrs.validators.instance_of(str),
    )

    footer: str = attrs.field(
        init=False,
        default="\n\n</DL><p>\n",
        validator=attrs.validators.instance_of(str),
    )

    def write_file(self, csv_file_path: Path, csv_records: list[CSVRecord]):
        """Write out all of the csv_records to the html file."""
        html_file_path = csv_file_path.with_suffix(".html")
        with html_file_path.open(mode="w", encoding="utf-8") as f:
            f.write(self.header)
            for csv_record in csv_records:
                f.write(csv_record.as_html)
            f.write(self.footer)


@attrs.frozen
class CSVRecord:
    """One row/record of a CSV file."""

    title: str = attrs.field(
        validator=attrs.validators.instance_of(str),
    )

    url: str = attrs.field(
        validator=attrs.validators.instance_of(str),
    )

    time_added: int = attrs.field(
        converter=int,
        validator=attrs.validators.instance_of(int),
    )

    tags: list = attrs.field(
        converter=lambda value: value.split("|") if value else [],
        validator=attrs.validators.instance_of(list),
    )

    status: str = attrs.field(
        validator=attrs.validators.instance_of(str),
    )

    dt_time_added: datetime = attrs.field(
        init=False,
        default=attrs.Factory(
            takes_self=True,
            factory=lambda self: datetime.fromtimestamp(self.time_added),
        ),
        validator=attrs.validators.instance_of(datetime),
    )

    @property
    def clean_title(self):
        return unidecode(self.title)

    @property
    def clean_url(self):
        return unidecode(self.url.strip().replace(" ", "%20"))

    @property
    def as_html(self):
        toread = "1" if self.status == "unread" else "0"
        tags = self.tags.copy()
        if self.status == "archive":
            tags.append("linkding:bookmarks.archived")
        return (
            f'\n<DT><A HREF="{self.clean_url}" ADD_DATE="{self.time_added}" '
            f'LAST_MODIFIED="{self.time_added}" PRIVATE="1" TOREAD="{toread}" '
            f'TAGS="{",".join(tags)}">{self.clean_title}</A>\n'
        )

@attrs.define
class CSVFile:
    """A CSV file (as exported from Mozilla Pocket)."""

    file_path: Path = attrs.field(
        validator=attrs.validators.instance_of(Path),
    )

    def row_iterator(self) -> Iterator[list[str]]:
        """Context-managed generator that yields rows from the CSV file."""
        with self.file_path.open(mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row

    def get_csv_records(self) -> list[CSVRecord]:
        return [CSVRecord(**row_dict) for row_dict in self.row_iterator()]

    def __str__(self):
        return str(self.file_path)


def main():
    cfg = Config()
    for csv_file_path in cfg.pocket_export_path.glob("*.csv"):
        csv_file = CSVFile(file_path=csv_file_path)
        csv_records = csv_file.get_csv_records()
        print(f"Got {len(csv_records)} CSV Records for {csv_file}")
        BookmarkFile().write_file(csv_file_path=csv_file_path, csv_records=csv_records)


if __name__ == "__main__":
    main()
