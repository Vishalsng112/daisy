# This file is reponsible by parsing a Dafny file retrieving the AST
# It must also implement functions allowying it to retrieve
  # Assertions source position
  # Insert assertions at a given position in another source file

from cairosvg.parser import Element
from src.utils.assertion_method_classes import FileInfo, MethodInfo, AssertionInfo, assertionGroup

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


def _parse_int(text: str | None, default: int = -1) -> int:
    """Parse an int from XML text, stripping whitespace. Returns default on failure."""
    if(text is None):
        return default
    try:
        return int(text.strip())
    except (ValueError, TypeError):
        return default
    

def extract_assertion(dafny_file_assertion_all_xml: str, file_path: Path) -> FileInfo:
    """
    Parse XML produced by (modified) Dafny verification and return the FileInfo object
    representing the information for that file.

    Args:
        dafny_file_assertion_all_xml: XML text (string) containing a <program> root.
        file_path: Path to the source file from which byte segments will be extracted.

    Returns:
        assert_method_class.FileInfo: populated FileInfo with MethodInfo and AssertionInfo.
    """
    # Helper to get stripped text of a child element
    def child_text(elem: ET.Element, tag: str) -> Optional[str]:
        c = elem.find(tag)
        return c.text.strip() if (c is not None and c.text) else None


    root: Element[str] = ET.fromstring(dafny_file_assertion_all_xml)

    file_info = FileInfo(file_path)
    method_tags: set[str] = {"method", "function", "Method", "Function"}

    methods_to_process: list[Element[str]] = []
    if root.tag in method_tags:
        methods_to_process.append(root)

    for tag in method_tags:
        methods_to_process.extend(root.findall(f".//{tag}"))

    for elem in methods_to_process:
        name = child_text(elem, "name") or ""
        start_pos = _parse_int(child_text(elem, "start_pos"))
        end_pos = _parse_int(child_text(elem, "end_pos"))

        method = MethodInfo(start_pos, end_pos, name, file_info)

        assertions: list[AssertionInfo] = []
        for asrt in elem.findall(".//assertion"):
            asstype = child_text(asrt, "type") or ""
            astart = _parse_int(child_text(asrt, "start_pos"))
            aend = _parse_int(child_text(asrt, "end_pos"))
            assertions.append(AssertionInfo(astart, aend, asstype, method))

        if assertions:
            method.add_assertion_group(assertions)

        file_info.add_method(method)

    return file_info

 
def replace_assertion_by(dafny_file_bytes: bytes, assertion_info: AssertionInfo, substitute : str ="") -> tuple[bytes, str]:
    posi = assertion_info.start_pos
    pose = assertion_info.end_pos

    plus_padding = 1

    new_raw_bytes: bytes = dafny_file_bytes[:posi] + substitute.encode("utf-8") + dafny_file_bytes[pose+plus_padding:]
    return new_raw_bytes, new_raw_bytes.decode("utf-8")


def get_assertion_bytes_and_string(dafny_file_bytes : bytes, assertion_info : AssertionInfo) -> tuple[bytes, str]:
    posi = assertion_info.start_pos
    pose = assertion_info.end_pos
    substring_bytes = dafny_file_bytes[posi:pose+1]
    substring_text = substring_bytes.decode("utf-8")
    return substring_bytes, substring_text


def get_method_bytes_and_string(dafny_file_bytes : bytes, method_info : MethodInfo)-> tuple[bytes, str]:
    posi = method_info.start_pos
    pose = method_info.end_pos
    substring_bytes = dafny_file_bytes[posi:pose+1]
    substring_text = substring_bytes.decode("utf-8")
    return substring_bytes, substring_text  


def replace_assertion_in_method_by(method_file_bytes : bytes, method_info : MethodInfo, assertion_info : AssertionInfo, substitute : str =""):
    posi = assertion_info.start_pos  - method_info.start_pos
    pose = assertion_info.end_pos - method_info.start_pos

    plus_padding = 1
    new_raw_bytes = method_file_bytes[:posi] + substitute.encode("utf-8") + method_file_bytes[pose+plus_padding:]
    return new_raw_bytes, new_raw_bytes.decode("utf-8")

# It is expected for the assertions positions to be sorted
# if method_info different than {} it also return method replaced info
def remove_empty_lines_function(text: str) -> str:
    return "\n".join(line for line in text.split("\n") if line.strip())
    
from src.utils.assertion_method_classes import get_method_from_assertion_group
def get_file_and_method_without_assertion_group(dafny_file : Path, assertions_group: assertionGroup, remove_empty_lines : bool = False):
        method_info = get_method_from_assertion_group(assertions_group)
        #Pick a method remove all assertions one by one and see if working
        with open(dafny_file, "rb") as f:
          content_bytes = f.read()

        # Assertions Sorted
        sorted_assertions_info:  assertionGroup = sorted(assertions_group, key=lambda x: x.start_pos)
        # If a assertion is of type By_assertion (i cannot remove assertions that are inside it if i will remove it:)
        # Logic to remove them
        assertions_to_remove: assertionGroup  = []
        inside_by_assertions = 0
        end_of_by_assertions = 0
        for assertion in sorted_assertions_info:
            if(not inside_by_assertions):
                assertions_to_remove.append(assertion)
            else:
                if(assertion.end_pos > end_of_by_assertions):
                    assertions_to_remove.append(assertion)
            if(assertion.type == "By_assertion"):
                inside_by_assertions = 1
                end_of_by_assertions = assertion.end_pos
        # The assertions should be in reverse order in order the remove one by one from the end
        assertions_to_remove = sorted(assertions_to_remove, key=lambda x: x.start_pos, reverse=True)

        new_file_bytes = content_bytes[:]
        for assertion in assertions_to_remove:
            new_file_bytes, _ = replace_assertion_by(new_file_bytes, assertion)

        new_file_str = new_file_bytes.decode("utf-8")
        if(remove_empty_lines):
            new_file_str = remove_empty_lines_function(new_file_str)
        
        method_bytes, _ = get_method_bytes_and_string(content_bytes, method_info)
        for assertion in assertions_to_remove:
            method_bytes, _ = replace_assertion_in_method_by(method_bytes,method_info,assertion)
        method_str = method_bytes.decode("utf-8")
        if(remove_empty_lines):
            method_str = remove_empty_lines_function(method_str)
        return new_file_str, method_str
