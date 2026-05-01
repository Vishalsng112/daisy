import re


def extract_error_blocks(input_string: str):
    error_pattern = r"^.*Error:.*$"
    warning_pattern = r"^.*Warning:.*$"

    lines = input_string.splitlines()
    error_blocks: list[str] = []
    current_block: list[str] = []

    for line in lines:
        if re.match(error_pattern, line):
            if current_block != []:
                error_blocks.append("\n".join(current_block))
            current_block = [line]
        elif re.match(warning_pattern, line):
            if current_block != []:
                error_blocks.append("\n".join(current_block))
            current_block = []
        elif current_block != []:
            current_block.append(line)

    if current_block != []:
        error_blocks.append("\n".join(current_block))

    return "\n\n".join(error_blocks)
