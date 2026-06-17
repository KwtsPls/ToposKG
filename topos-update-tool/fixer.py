#!/usr/bin/env python3
"""Process RDF N-Triples (.nt) files line by line.

This script:
1. Reads an input .nt file.
2. Parses each triple line into subject, predicate, and object.
3. Exposes the object for custom processing.
4. Writes processed triples to a new output file.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from typing import Optional, Tuple


import re
from typing import Optional, Tuple


# We only care about capturing the first two <...> blocks.
# The '.*' at the end just grabs the rest of the raw string for us to handle manually.
STRICT_FRONT_RE = re.compile(r"^<([^>]+)>\s+<([^>]+)>\s+(.*)$")

def parse_nt_line_hybrid(line: str) -> Optional[Tuple[str, str, str]]:
    """Parse an N-Triples line using regex for URIs and manual string slicing for the object."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    match = STRICT_FRONT_RE.match(stripped)
    if not match:
        return None

    subject, predicate, raw_remainder = match.groups()

    # Manually clean up the object remainder
    raw_remainder = raw_remainder.strip()

    # Check if it ends with a period and slice it off
    if raw_remainder.endswith("> .") or raw_remainder.endswith("\" .") or (raw_remainder.endswith(" .") and raw_remainder[-5] == '@' and raw_remainder[-6] == '"'):
        # [:-1] removes the trailing '.', then we strip any remaining trailing whitespace
        obj = raw_remainder[:-1].rstrip()
        return subject, predicate, obj

    # If it doesn't end with a period, it's a multi-line N-Triple
    if raw_remainder.startswith("\""):    
        global COLLECTION_MODE
        COLLECTION_MODE = True
        return subject, predicate, raw_remainder
    
    raise ValueError(f"Line does not conform to N-Triples format: {line.strip()}")


def process_object(obj: str) -> str:
    if obj.startswith("<") and obj.endswith(">"):
        # It's a URI, process it.
        return obj.replace(" ", "_")  # Replace spaces with underscores in the URI.
    return obj  # Return the object unchanged if it's not a URI.


def process_file(input_path: str, output_path: str) -> None:
    processed_count = 0
    skipped_count = 0
    changed = 0
    
    global COLLECTION_MODE

    with open(input_path, "r", encoding="utf-8") as in_f, open(
        output_path, "w", encoding="utf-8"
    ) as out_f:
        collection: str = ""
        for line_number, line in enumerate(in_f, start=1):
            if COLLECTION_MODE:
                # If we're in collection mode, we need to collect lines until we find the closing period.
                if line.strip().endswith("\" ."):
                    COLLECTION_MODE = False
                    collection += line.strip()[:-2].rstrip()  # Remove the trailing ' .'
                    obj = collection
                    # Now process the collected object
                else:
                    collection += line.strip() + " "
                    continue  # Continue collecting lines
            else:
                parsed = parse_nt_line_hybrid(line)
                if parsed is None:
                    # Keep original line if it is blank/comment/non-triple.
                    out_f.write(line)
                    print(f"Line {line_number} skipped (not a valid triple): {line.strip()}")
                    skipped_count += 1
                    continue
                subject, predicate, obj = parsed
                if COLLECTION_MODE:
                    collection += obj + " "
                    continue
                
            subject = f"<{subject}>"
            predicate = f"<{predicate}>"

            # Object is the 3rd part of the SPO triple.
            new_subj = process_object(subject)
            new_pred = process_object(predicate)
            new_obj = process_object(obj)

            if new_obj != obj or new_subj != subject or new_pred != predicate:
                changed += 1
                changed_predicate = "PREDICATE" if new_pred != predicate else ""
                changed_subject = "SUBJECT" if new_subj != subject else ""
                changed_object = "OBJECT" if new_obj != obj else ""
                changes = ", ".join(filter(None, [changed_subject, changed_predicate, changed_object]))
                print(f"Line {line_number} changed ({changes}):\n'{subject} {predicate} {obj} .' -> '{new_subj} {new_pred} {new_obj} .'")
                
            if collection:
                print(f"Collected: {collection.strip()}")
                collection = ""  # Reset collection after processing

            out_f.write(f"{new_subj} {new_pred} {new_obj} .\n")
            processed_count += 1

    print(f"Done. Processed triples: {processed_count}")
    print(f"Changed triples: {changed}")
    print(f"Copied without parsing: {skipped_count}")
    print(f"Output written to: {output_path}")
    
    if skipped_count > 0:
        raise ValueError(f"Some lines were skipped during processing. Check the output file for details. Skipped count: {skipped_count}")
    
    # replace the original file with the processed file
    shutil.move(output_path, input_path)


def default_output_path(input_path: str) -> str:
    base, ext = os.path.splitext(input_path)
    if ext.lower() == ".nt":
        return f"{base}.processed{ext}"
    return f"{input_path}.processed.nt"


def process_path(input_path: str, output_path: Optional[str] = None) -> None:
    """Process a single file or recursively process all .nt files in a directory.

    If `input_path` is a directory, walks it recursively and processes every
    file whose name ends with `.nt` (case-insensitive). When `output_path` is
    provided and is a directory, the processed files are written into the
    directory preserving relative paths. When `output_path` is provided for a
    single input file and points to a directory, the output file will be
    written into that directory with the same base name.
    """
    if os.path.isdir(input_path):
        base_in = os.path.abspath(input_path)
        base_out = None
        if output_path:
            # If user supplied an output path, it must be a directory when input is a dir
            if os.path.exists(output_path) and not os.path.isdir(output_path):
                raise ValueError("When input is a directory, --output must be a directory if provided")
            base_out = output_path

        for root, _dirs, files in os.walk(base_in):
            for fname in files:
                if not fname.lower().endswith(".nt"):
                    continue
                in_file = os.path.join(root, fname)
                if base_out:
                    rel = os.path.relpath(in_file, base_in)
                    out_file = os.path.join(base_out, rel)
                    out_dir = os.path.dirname(out_file)
                    os.makedirs(out_dir, exist_ok=True)
                    # ensure extension is .nt
                    if not out_file.lower().endswith(".nt"):
                        out_file = f"{out_file}.nt"
                else:
                    out_file = default_output_path(in_file)

                print(f"Processing: {in_file} -> {out_file}")
                process_file(in_file, out_file)
    else:
        # Single file input
        if output_path and os.path.isdir(output_path):
            # write into the provided directory preserving filename
            out_file = os.path.join(output_path, os.path.basename(input_path))
            if not out_file.lower().endswith(".nt"):
                out_file = f"{out_file}.nt"
        else:
            out_file = output_path or default_output_path(input_path)

        print(f"Processing: {input_path} -> {out_file}")
        process_file(input_path, out_file)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process object (3rd element) of each RDF N-Triples line."
    )
    parser.add_argument("input_file", help="Path to input .nt file or directory")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to output file (default: <input>.nt)",
    )
    args = parser.parse_args()

    # Delegate to process_path which handles both files and directories.
    try:
        process_path(args.input_file, args.output)
    except Exception as exc:  # pragma: no cover - surface errors to user
        print(f"Error: {exc}")
        raise


if __name__ == "__main__":
    COLLECTION_MODE = False
    main()
