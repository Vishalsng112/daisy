from __future__ import annotations 
from src.utils.assertion_method_classes import FileInfo, assertionGroup, MethodInfo 
from src.utils.dafny_read_assertions_xml import extract_assertion
import os 
from pathlib import Path


class Dataset:
    """
    Represents a collection of parsed FileInfo objects.

    Use the provided classmethods to construct:
      - Dataset.from_dataset_all(path)
      - Dataset.from_dataset_assertion_groups(path)
    """

    def __init__(self, files: list[FileInfo], dataset_path: Path) -> None:
        # private-ish constructor: factories should be used
        self.dataset_path = dataset_path
        self.files: list[FileInfo] = files

    # -------------------------
    # Factory: dataset all
    # -------------------------
    @classmethod
    def from_dataset_all(cls, dataset_all_path: Path) -> "Dataset":
        """
        Construct Dataset where each dafny file folder contains an 'assert.xml'
        describing the whole file. For each folder with assert.xml we call
        extract_assertion(xml, original_program_path) and store the returned FileInfo.
        """
        files: list[FileInfo] = []
        dataset_all_path = Path(dataset_all_path)

        for dafny_file_folder in os.listdir(dataset_all_path):
            dafny_file_folder_path = dataset_all_path / dafny_file_folder
            if not dafny_file_folder_path.is_dir():
                continue

            info_xml_path = dafny_file_folder_path / "assert.xml"
            dafny_file_path = dafny_file_folder_path / "original_program.dfy"

            # Prefer to pass the actual source file path to extract_assertion,
            # because FileInfo needs it to load bytes/text.
            if info_xml_path.exists() and dafny_file_path.exists():
                with open(info_xml_path, "r", encoding="utf-8") as xml_file:
                    xml_content = xml_file.read()
                file_obj = extract_assertion(xml_content, dafny_file_path)
                files.append(file_obj)

        return cls(files, dataset_path=dataset_all_path)

    # -------------------------
    # Factory: dataset assertion groups
    # -------------------------
    @classmethod
    def from_dataset_assertion_groups(cls, dataset_assertion_group_path: Path) -> "Dataset":
        """
        Construct Dataset from the 'assertion_group' layout where each method_start_*
        subfolder contains an info.xml describing a single method+assertion-group.
        For every such subfolder we create a FileInfo (one per subfolder).
        """
        files: list[FileInfo] = []
        dataset_assertion_group_path = Path(dataset_assertion_group_path)

        for dafny_file_folder in os.listdir(dataset_assertion_group_path):
            dafny_file_folder_path = dataset_assertion_group_path / dafny_file_folder
            if not dafny_file_folder_path.is_dir():
                continue

            # find all method_start_* subdirs inside this folder
            subdirs = [
                subdir for subdir in os.listdir(dafny_file_folder_path)
                if (dafny_file_folder_path / subdir).is_dir() and subdir.startswith("method_start_")
            ]

            # the original program file for this folder (source used to make FileInfo)
            dafny_file_path = dafny_file_folder_path / "original_program.dfy"
            if not dafny_file_path.exists():
                # skip if source file missing
                continue

            for subdir in subdirs:
                info_xml_path = dafny_file_folder_path / subdir / "info.xml"
                if not info_xml_path.exists():
                    continue
                with open(info_xml_path, "r", encoding="utf-8") as xml_file:
                    xml_content = xml_file.read()
                # Important: pass the original_program.dfy path to extract_assertion
                file_obj = extract_assertion(xml_content, dafny_file_path)
                files.append(file_obj)

        return cls(files, dataset_path=dataset_assertion_group_path)

    # -------------------------
    # Helpers
    # -------------------------
    def get_all_assertion_groups(self) -> list[assertionGroup]:
        """
        Flatten and return all assertion groups across all files and methods.
        """
        dataset_assertion_groups: list[assertionGroup] = []
        for file in self.files:
            for method in file.methods:
                for assertion_group in method.assertion_groups:
                    dataset_assertion_groups.append(assertion_group)
        return dataset_assertion_groups

    def get_all_methods(self) -> list[MethodInfo]:
        """Return a flat list of all MethodInfo objects."""
        methods: list[MethodInfo] = []
        for f in self.files:
            methods.extend(f.methods)
        return methods
