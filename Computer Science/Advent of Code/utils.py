"""Utilities for Advent of Code 2022"""

import sys
from typing import Any

import pyperclip


def clip(obj: Any) -> str:
    """Copy str(obj) onto clipboard.

    Returns the string copied to the clipboard.
    """

    string_obj = str(obj)
    pyperclip.copy(string_obj)
    return string_obj


def get_input(script_name: str) -> str:
    """Takes __file__ from script, returns the input."""
    input_file = script_name[:script_name.rfind('.')] + ".txt"
    try:
        with open(input_file, "r", encoding="utf-8") as file_ptr:
            input_string = file_ptr.read()
    except OSError:
        input_string = pyperclip.paste().rstrip("\n")
        with open(input_file, "w", encoding="utf-8") as file_ptr:
            file_ptr.write(input_string)
    return input_string


def print(obj: Any) -> None:
    """Print str(obj), then copy it onto the clipboard."""
    sys.stdout.write(clip(obj) + "\n")
