#!/usr/bin/env python3
import os
import re
import sys
from typing import Iterable


def extract_snippets_from_source(source_text: bytes):
    prev_start: int | None = None
    prev_type: str | None = None
    for m in re.finditer(rb'(/\*\s*USER CODE (BEGIN|END)([^*]*)\*/)', source_text):
        full_comment, begin_or_end, snippet_type_b = m.groups()
        snippet_type = snippet_type_b.decode('utf-8').strip()
        begin_or_end = begin_or_end.decode('utf-8')
        if begin_or_end == 'BEGIN':
            if prev_start is not None:
                print("WARNING: USER CODE BEGIN without matching END", prev_type, file=sys.stderr)
                # snippet = source_text[prev_start:m.start()]
                yield snippet_type, prev_start, m.start()  # yield snippet_type, snippet
            prev_start = m.start()
            prev_type = snippet_type
        elif prev_start is not None and prev_type == snippet_type:
            # snippet = source_text[prev_start:m.end()]
            # yield snippet_type, snippet
            yield snippet_type, prev_start, m.end()
            prev_start = None
        else:
            print(f"WARNING: USER CODE END without matching BEGIN ignored: {full_comment}", file=sys.stderr)


def extract_snippets_from_source_all(source_text: bytes):
    return list(extract_snippets_from_source(source_text))


def exec_rewrites(source_text: bytes, rewrites: list[tuple[int, int, bytes]]):
    if not rewrites:
        return source_text
    # start_text = source_text[:rewrites[0][0]]
    last_end = 0
    parts = []
    for start, end, replace_with_text in rewrites:
        s1 = source_text[last_end:start]
        s2 = replace_with_text
        last_end = end
        parts.append(s1)
        parts.append(s2)
    suffix_text = source_text[rewrites[-1][1]:]
    parts.append(suffix_text)
    return b"".join(parts)


def rewrite_snippets(rewrite_me: bytes, snippets_source: bytes, snippets: Iterable[tuple[str, int, int]]):
    snippetmap: dict[str, bytes] = {snippet_type: snippets_source[start:end] for snippet_type, start, end in snippets}
    rewrites = []
    for snippet_type, start, end in extract_snippets_from_source(rewrite_me):
        replace_with = snippetmap.get(snippet_type)
        if replace_with is not None:
            rewrites.append((start, end, replace_with))
    return exec_rewrites(rewrite_me, rewrites)


def dirwalk_csource(source_dir: str):
    for root, dirs, files in os.walk(source_dir, topdown=True):
        for file in files:
            if is_c_source(file):
                yield os.path.join(root, file)


def is_c_source(file):
    return any((file.lower()).endswith(ext) for ext in ('.c', '.cc', '.cpp', '.h', '.hh', '.hpp'))


def detect_line_ends(source_code: bytes):
    if b"\r\n" in source_code:
        return b"\r\n"
    elif b"\r" in source_code:
        return b"\r"
    else:
        return b"\n"


def f2snip(filename: str):
    return filename + ".snip"


def snip2f(snip_filename: str):
    if snip_filename.endswith(".snip"):
        return snip_filename.removesuffix(".snip")
    return None


def is_snip(snip_filename: str):
    return snip2f(snip_filename) is not None


def makedirs_for_file(filename: str):
    os.makedirs(os.path.dirname(filename), exist_ok=True)


def action_extract_inplace(source_dir: str, target_dir: str):
    for srcfile in dirwalk_csource(source_dir):
        if is_snip(srcfile):
            continue
        original_src = os.path.join(target_dir, os.path.relpath(f2snip(srcfile), source_dir))
        with open(srcfile, 'rb') as source_file:
            source = source_file.read()
            line_ends = detect_line_ends(source)

            snippets = extract_snippets_from_source_all(source)
            if not snippets:
                try:
                    os.remove(original_src)
                except FileNotFoundError:
                    pass  # It's ok - we do the equivalent of rm -f

            content = line_ends.join(source[start:end] for _, start, end in snippets)
            print(srcfile)
            makedirs_for_file(original_src)
            with open(original_src, 'bw') as out:
                out.write(content)
                out.write(line_ends)


def action_rebase(source_dir: str, target_dir: str):
    for srcfile in dirwalk_csource(source_dir):
        original_filename = f2snip(srcfile)
        if original_filename is None:
            continue
        original_file = os.path.join(target_dir, os.path.relpath(original_filename, source_dir))

        with open(srcfile, 'rb') as snippets_source_f:
            snippets_source = snippets_source_f.read()
            snippets = extract_snippets_from_source_all(snippets_source)
        if not snippets:
            continue

        makedirs_for_file(original_file)
        with open(original_file, 'r+b') as orig_source_f:
            orig_source = orig_source_f.read()
            new_text = rewrite_snippets(orig_source, snippets_source, snippets)
            orig_source_f.seek(0)
            orig_source_f.write(new_text)
            orig_source_f.truncate()


def action_findall(source_dir: str):
    for srcfile in dirwalk_csource(source_dir):
        if is_snip(srcfile):
            continue
        with open(srcfile, 'rb') as source_file:
            source = source_file.read()
            line_end = detect_line_ends(source)
            snippets = extract_snippets_from_source_all(source)

            if not snippets:
                continue

            content = line_end.join(source[start:end] for _, start, end in snippets)
            print(srcfile + ":")
            print(content.decode('utf-8'))


def main(argv: list[str]):
    import argparse
    parser = argparse.ArgumentParser(prog='stm32cube_grovel',
                                     description='Extracts /* USER CODE BEGIN */ ... /* USER CODE END */ snippets from STM32CubeIde Projects',
                                     epilog="Copyright (C) 2022 Nikita Chancellorsville")
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('-p', '--print-all', action='store_true',
                              help="Print all user code snippets along with their filenames")
    action_group.add_argument('-x', '--extract', action='store_true',
                              help="Extract all user code snippets in place into $FILE.snip files in the project")
    action_group.add_argument('-r', '--rebase', action='store_true',
                              help="Take all $NAME.snip files and use them to replace the corresponding snippets in rebase_target")
    parser.add_argument('source_dir', nargs='?', default='.')
    parser.add_argument('rebase_target', nargs='?')

    args = parser.parse_args(argv)
    if args.rebase and args.rebase_target is None:
        parser.error("rebase_target required with --rebase")
    elif not (args.rebase or args.extract) and args.rebase_target is not None:
        parser.error("rebase_target can only be specified with --rebase")

    source_dir: str = args.source_dir
    if args.print_all:
        action_findall(source_dir)
    elif args.extract:
        action_extract_inplace(source_dir, args.rebase_target or source_dir)
    elif args.rebase:
        action_rebase(source_dir, args.rebase_target)


if __name__ == '__main__':
    main(sys.argv[1:])
