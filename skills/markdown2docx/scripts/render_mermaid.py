#!/usr/bin/env python3
"""Render Mermaid diagrams in a markdown file to PNG via mermaid.ink API.

Usage:
    python render_mermaid.py input.md output_dir/
    
Finds ```mermaid ... ``` blocks, renders each to PNG, and
replaces them with ![alt](filename.png) references.
Returns the modified markdown on stdout.
"""

import sys, os, re, base64, urllib.request

def render_mermaid(code: str, output_path: str) -> bool:
    """Render mermaid code to PNG. Returns True on success."""
    encoded = base64.urlsafe_b64encode(code.encode('utf-8')).decode('utf-8')
    url = f'https://mermaid.ink/img/{encoded}?type=png'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'md2docx/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(output_path, 'wb') as f:
                f.write(resp.read())
        return True
    except Exception as e:
        print(f"  WARNING: failed to render mermaid: {e}", file=sys.stderr)
        return False

def process_markdown(input_path: str, output_dir: str) -> str:
    """Process markdown file, render mermaid diagrams, return modified text."""
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Find all mermaid code blocks
    pattern = r'```mermaid\n(.*?)```'
    count = 0
    
    def replace_mermaid(match):
        nonlocal count
        code = match.group(1)
        filename = f"diagram_{count:02d}.png"
        filepath = os.path.join(output_dir, filename)
        if render_mermaid(code.strip(), filepath):
            count += 1
            return f'![{filename}]({filename})'
        else:
            # Keep original as code block if render fails
            return match.group(0)
    
    content = re.sub(pattern, replace_mermaid, content, flags=re.DOTALL)
    print(f"Rendered {count} mermaid diagrams", file=sys.stderr)
    return content

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: render_mermaid.py input.md [output_dir]", file=sys.stderr)
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(input_path)
    
    result = process_markdown(input_path, output_dir)
    print(result)
