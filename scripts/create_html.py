#######
# Export script 
# This script takes in a directory of text files representing chapters
# and generates a single HTML pages for all of them, including navigation elements. 
# 
# As of 2025-12-26, it's good but doesn't work well with Safari reader mode. 
####### 

from pathlib import Path
import html
import re


def natural_sort_key(path):
    """Extract numbers from filename for natural sorting"""
    filename = path.name
    # Extract all numbers from the filename
    numbers = re.findall(r'\d+', filename)
    if numbers:
        return int(numbers[0])
    return 0


def create_html_from_chapters(input_dir, output_filename="compiled_chapters.html"):
    """Create a single HTML file from all text files in input_dir"""
    print(f"\n{'='*60}")
    print(f"Creating HTML from chapters in {input_dir}")
    print('='*60)
    
    input_path = Path(input_dir)
    
    # Get all text files sorted naturally (ch1, ch2, ..., ch10, ch11, ch12)
    chapter_files = sorted(input_path.glob("*.txt"), key=natural_sort_key)
    
    if not chapter_files:
        print("  ⚠️  No text files found in input directory")
        return None
    
    # Start building HTML
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Compiled Chapters</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
            background-color: #fff;
        }
        
        .toc {
            margin: 40px 0;
            padding: 20px;
            background-color: #f5f5f5;
            border-radius: 8px;
        }
        
        .toc h2 {
            margin-top: 0;
            font-size: 1.5em;
        }
        
        .toc ul {
            list-style-type: none;
            padding-left: 0;
        }
        
        .toc li {
            margin: 10px 0;
        }
        
        .toc a {
            color: #0066cc;
            text-decoration: none;
        }
        
        .toc a:hover {
            text-decoration: underline;
        }
        
        .chapter {
            margin: 80px 0 60px 0;
        }
        
        .chapter:first-of-type {
            margin-top: 40px;
        }
        
        .chapter-title {
            font-size: 2em;
            text-align: center;
            margin: 0 0 30px 0;
            padding-top: 20px;
            color: #1a1a1a;
            border-top: 3px double #ddd;
        }
        
        .chapter:first-of-type .chapter-title {
            border-top: none;
        }
        
        .chapter-content p {
            margin: 1.2em 0;
            text-align: justify;
        }
        
        @media print {
            .toc {
                display: none;
            }
        }
    </style>
</head>
<body>
    <h1 style="text-align: center; margin: 40px 0;">Compiled Chapters</h1>
    
    <div class="toc" id="toc">
        <h2>Table of Contents</h2>
        <ul>
"""
    
    # Read all chapters and build content
    chapters_data = []
    for i, chapter_file in enumerate(chapter_files):
        print(f"  Reading {chapter_file.name}...")
        
        with open(chapter_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            continue
        
        # First line is the title
        title = lines[0].strip()
        content = ''.join(lines[1:]).strip()
        
        chapter_id = f"chapter-{i+1}"
        chapters_data.append({
            'id': chapter_id,
            'title': title,
            'content': content,
            'file': chapter_file.name
        })
    
    # Build table of contents
    for chapter in chapters_data:
        html_content += f'            <li><a href="#{chapter["id"]}">{html.escape(chapter["title"])}</a></li>\n'
    
    html_content += """        </ul>
    </div>
    
"""
    
    # Build chapter content
    for i, chapter in enumerate(chapters_data):
        print(f"  Adding {chapter['file']} to HTML...")
        
        html_content += f'    <div class="chapter" id="{chapter["id"]}">\n'
        html_content += f'        <h2 class="chapter-title">{html.escape(chapter["title"])}</h2>\n'
        html_content += '        <div class="chapter-content">\n'
        
        # Split content into paragraphs
        paragraphs = chapter['content'].split('\n\n')
        for para in paragraphs:
            if para.strip():
                # Escape HTML and convert line breaks within paragraphs
                clean_para = html.escape(para.strip()).replace('\n', '<br>\n            ')
                html_content += f'            <p>{clean_para}</p>\n'
        
        html_content += '        </div>\n'
        html_content += '    </div>\n\n'
    
    # Close HTML
    html_content += """</body>
</html>"""
    
    # Write HTML file
    output_path = input_path / output_filename
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n✓ HTML created: {output_path}")
    print(f"  Total chapters: {len(chapters_data)}")
    return output_path


if __name__ == "__main__":
    import sys
    
    # Default to outputs/rekindling directory, or use command line argument
    if len(sys.argv) > 1:
        input_dir = sys.argv[1]
    else:
        input_dir = "../outputs/rekindling"
    
    # Optional: custom HTML filename
    if len(sys.argv) > 2:
        output_filename = sys.argv[2]
    else:
        output_filename = "compiled_chapters.html"
    
    result = create_html_from_chapters(input_dir, output_filename)
    
    if result:
        print(f"\nOpen the file in Safari and use Reader Mode for the best experience!")
