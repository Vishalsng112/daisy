"""Generate assertion-removal test cases for a method.

For each combination of assertions to remove (w/o-1, w/o-2, w/o-all),
removes them from the program, runs Dafny, and saves the broken program
+ verifier output + info.xml when verification fails.
"""

from __future__ import annotations

import itertools
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from pathlib import Path

from src.utils.assertion_method_classes import AssertionInfo, MethodInfo, assertionGroup
from src.utils.dafny_read_assertions_xml import get_file_and_method_without_assertion_group
from src.utils.dafny_runner import DafnyStatus, run_dafny_from_text


def _create_assertion_xml(
    number_to_remove: int,
    assertions_to_remove: list[AssertionInfo],
    method_info: MethodInfo,
    output_path: Path,
    group_id: int,
) -> None:
    """Write info.xml describing the assertion group."""
    root = ET.Element("method")
    ET.SubElement(root, "name").text = method_info.method_name
    ET.SubElement(root, "start_pos").text = str(method_info.start_pos)
    ET.SubElement(root, "end_pos").text = str(method_info.end_pos)

    ag = ET.SubElement(root, "assertion_group")
    ET.SubElement(ag, "id").text = str(group_id)
    ET.SubElement(ag, "number_assertions").text = str(number_to_remove)

    for a in assertions_to_remove:
        ae = ET.SubElement(ag, "assertion")
        ET.SubElement(ae, "type").text = a.type
        ET.SubElement(ae, "start_pos").text = str(a.start_pos)
        ET.SubElement(ae, "end_pos").text = str(a.end_pos)

    rough = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(pretty, encoding="utf-8")


def _test_program_without_assertions(
    dafny_exec: Path,
    dafny_file: Path,
    assertions_group: list[AssertionInfo],
) -> tuple[DafnyStatus, str, str, str, str]:
    """Remove assertions from program, run Dafny, return (status, stdout, stderr, file_text, method_text)."""
    new_file_text, method_text = get_file_and_method_without_assertion_group(
        dafny_file, assertions_group, remove_empty_lines=True,
    )
    status, stdout, stderr = run_dafny_from_text(dafny_exec, new_file_text)
    return status, stdout, stderr, new_file_text, method_text


def _process_assertion_combinations(
    assertion_infos: list[AssertionInfo],
    n_to_remove: int,
) -> list[set[int]]:
    """Generate index sets for assertion combinations to test.

    n_to_remove == -1 means remove all.
    """
    ids = list(range(len(assertion_infos)))
    if n_to_remove == -1:
        return [{i for i in ids}]
    return [set(c) for c in itertools.combinations(ids, n_to_remove)]


def process_assertions_method(
    dafny_exec: Path,
    program_dst_folder: Path,
    program_path: Path,
    method_info: MethodInfo,
    max_assertions_to_remove: int,
) -> None:
    """Generate all assertion-removal test cases for one method.

    Args:
        dafny_exec: Dafny binary path.
        program_dst_folder: Output folder for this program.
        program_path: Path to original .dfy source.
        method_info: Method to process.
        max_assertions_to_remove: Max assertions to remove per combo (-1 = all).
    """
    assertion_groups_list = method_info.assertion_groups
    if not assertion_groups_list:
        return

    assertion_list = assertion_groups_list[0]
    group_id = 0

    def _process_set(
        assertions: list[AssertionInfo], n_remove: int, gid: int,
    ) -> tuple[list[assertionGroup], int]:
        found: list[assertionGroup] = []
        combos = _process_assertion_combinations(assertions, n_remove)

        for combo_ids in combos:
            to_remove = [assertions[i] for i in combo_ids]

            dir_suffix = (
                f"method_start_{method_info.start_pos}"
                + "".join(f"_as_start_{a.start_pos}_end_{a.end_pos}" for a in to_remove)
            )
            dst_dir = program_dst_folder / dir_suffix

            status, stdout, _, new_program, method_text = _test_program_without_assertions(
                dafny_exec, program_path, to_remove,
            )

            if status not in (DafnyStatus.VERIFIED, DafnyStatus.NOT_VERIFIED):
                print(f"Error running Dafny: {status}")

            if status == DafnyStatus.NOT_VERIFIED:
                dst_dir.mkdir(parents=True, exist_ok=True)
                (dst_dir / "method_without_assertion_group.dfy").write_text(method_text, encoding="utf-8")
                (dst_dir / "program_without_assertion_group.dfy").write_text(new_program, encoding="utf-8")
                (dst_dir / "verifier_output.txt").write_text(stdout, encoding="utf-8")
                _create_assertion_xml(n_remove, to_remove, method_info, dst_dir / "info.xml", gid)
                found.append(to_remove)
                gid += 1

        return found, gid

    if max_assertions_to_remove != -1:
        lvl1_groups, group_id = _process_set(assertion_list, 1, 0)
        lvl1_assertions = [g[0] for g in lvl1_groups]
        actual_max = min(max_assertions_to_remove, len(lvl1_assertions))
        for n in range(2, actual_max + 1):
            _, group_id = _process_set(lvl1_assertions, n, group_id)
    else:
        _process_set(assertion_list, -1, 0)
