from __future__ import annotations  

import os 
from pathlib import Path
from typing import TypeAlias


def substitute_a_given_pos_by_text(start_pos : int, end_pos: int, new_text: str, current_bytes: bytes)-> tuple [bytes, str]:
        plus_padding = 1
        s = start_pos 
        e = end_pos 
        new_bytes = (current_bytes[:s] + new_text.encode("utf-8") +
                         current_bytes[e + plus_padding:]) 
        return new_bytes , new_bytes.decode("utf-8")

class FileSegment:
    def __init__(self, start_pos : int, end_pos: int, file_path: Path):
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.file_path = file_path
        
        self.segment_bytes = b""
        self.segment_str = ""
        self.populate_bytes_and_string()

    def populate_bytes_and_string(self):
        with open(self.file_path, "rb") as f:
            file_bytes = f.read()
        
        self.segment_bytes = file_bytes[self.start_pos:self.end_pos+1]
        self.segment_str = self.segment_bytes.decode("utf-8")


class AssertionInfo(FileSegment):
    def __init__(self, start_pos: int, end_pos: int ,asstype: str, method : MethodInfo):
        super().__init__(start_pos, end_pos, method.file.file_path)
        self.type: str = asstype
        self.method: MethodInfo = method

    def __str__(self):
        return "ASSERT:" + self.segment_str + "START_POS:" + str(self.start_pos)
    
    def __repr__(self):
        return self.__str__()
    
assertionGroup: TypeAlias = list[AssertionInfo]

def get_method_from_assertion_group(assertion_group : assertionGroup) -> MethodInfo:
    if(len(assertion_group) == 0):
        raise ValueError("Assertion  Group is empty and that Cannot ever happen")
    return assertion_group[0].method

def get_file_from_assertion_group(assertion_group : assertionGroup) -> FileInfo:
    return assertion_group[0].method.file

def get_assertion_group_string_id(assertion_group : assertionGroup) -> str:
    method: MethodInfo = get_method_from_assertion_group(assertion_group)
    ret_string = f"method_start_{method.start_pos}"
    for assertion in assertion_group:
        ret_string += f"_as_start_{assertion.start_pos}_end_{assertion.end_pos}"
    return ret_string



class MethodInfo(FileSegment):
  def __init__(self, start_pos: int, end_pos: int, method_name: str, file: FileInfo):
        super().__init__(start_pos, end_pos, file.file_path)
        self.method_name = method_name
        self.file = file

        self.assertions_all  : list[AssertionInfo]= [] # File begining of XML 
        self.assertion_groups: list[assertionGroup] = [] # Two types of files files where assertion groups are retrieved

  # This adds a list of assertions corresponding to the helper
  # If helper level 1 [assertion_1]
  # If helper level 2 [assertion1,assertion_2]
  def add_assertion_group(self,assertion_group : assertionGroup):
        self.assertion_groups.append(assertion_group)

  def get_method_with_assertion_group_changed(self, assertion_group : assertionGroup, remove_empty_lines : bool, change_text : str) -> str:
    sorted_assertions = sorted(assertion_group, key=lambda x: x.start_pos)
    # Identify assertions to remove, ensuring nested assertions in "By_assertion" are properly handled
    removal_list: list[AssertionInfo] = []
    end_of_by_assertion = 0
    for assertion in sorted_assertions:
        if assertion.type == "By_assertion":
            end_of_by_assertion = assertion.end_pos
            removal_list.append(assertion)
        elif assertion.start_pos >= end_of_by_assertion:
            removal_list.append(assertion)
    # Remove assertions in reverse order to preserve indexing
    removal_list.sort(key=lambda x: x.start_pos, reverse=True)
    new_method_bytes: bytes = self.segment_bytes[:]
    for assertion in removal_list:
        new_method_bytes, _ = substitute_a_given_pos_by_text(
            assertion.start_pos - self.start_pos,
            assertion.end_pos - self.start_pos,
            change_text,
            new_method_bytes
        )
    new_method_str = new_method_bytes.decode("utf-8")
    return "\n".join(line for line in new_method_str.split("\n") if line.strip()) if remove_empty_lines else new_method_str






class FileInfo:
    def __init__(self,file_path : Path):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
          self.file_bytes = f.read()
        self.file_text =  self.file_bytes.decode("utf-8")

        self.start_pos = 0
        self.end_pos = len(self.file_bytes)+1

        self.methods: list[MethodInfo] = []

    def add_method(self,method : MethodInfo):
        self.methods.append(method)

    def substitute_method_with_text(self, method : MethodInfo, new_text : str):
        return substitute_a_given_pos_by_text(
            method.start_pos, 
            method.end_pos, 
            new_text, 
            self.file_bytes)
