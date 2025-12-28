"""
Utility functions.
"""

import re


def fixfname(filename: str) -> str:
    """
    Normalize filename to be Unix and Windows friendly.

    Transformations:
    - Replace non-alphanumeric chars (except '.') with underscore
    - Lowercase everything
    - Replace dots in name (not extension) with underscore
    - Remove leading/trailing underscores from name and extension
    - Collapse multiple underscores to single underscore

    Args:
        filename: Original filename (without path)

    Returns:
        Normalized filename
    """
    # Split name and extension
    if '.' in filename:
        # Find last dot for extension
        last_dot = filename.rfind('.')
        name = filename[:last_dot]
        ext = filename[last_dot + 1:]
    else:
        name = filename
        ext = ""

    # Replace non-alphanumeric (except dot) with underscore and lowercase
    name = re.sub(r'[^a-zA-Z0-9.]', '_', name).lower()
    ext = re.sub(r'[^a-zA-Z0-9]', '_', ext).lower()

    # Replace dots in name with underscores
    name = name.replace('.', '_')

    # Remove leading/trailing underscores
    name = name.strip('_')
    ext = ext.strip('_')

    # Collapse multiple underscores to single
    name = re.sub(r'_+', '_', name)
    ext = re.sub(r'_+', '_', ext)

    # Reconstruct filename
    if ext:
        return f"{name}.{ext}"
    else:
        return name
