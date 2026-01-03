#######
# Export script 
# This script takes in a directory of text files representing chapters
# and generates separate HTML pages for each, including navigation elements. 
# 
# As of 2025-12-26, it's the best for deploying on github pages.
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


def create_chapter_html_files(input_dir, output_subdir=None):
    """Create individual HTML files for each chapter with navigation"""
    print(f"\n{'='*60}")
    print(f"Creating HTML files from chapters in {input_dir}")
    print('='*60)
    
    input_path = Path(input_dir)
    
    # Determine output directory: public/{output_subdir or input_dir_name}/
    if output_subdir is None:
        output_subdir = input_path.name
    
    output_path = Path("../public") / output_subdir
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Get all text files sorted naturally (ch1, ch2, ..., ch10, ch11, ch12)
    chapter_files = sorted(input_path.glob("*.txt"), key=natural_sort_key)
    
    if not chapter_files:
        print("  ⚠️  No text files found in input directory")
        return None
    
    # Read all chapters first to build the dropdown
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
        
        # Generate HTML filename
        html_filename = chapter_file.stem + ".html"
        
        chapters_data.append({
            'index': i,
            'title': title,
            'content': content,
            'source_file': chapter_file.name,
            'html_file': html_filename
        })
    
    # Generate HTML for each chapter
    html_files_created = []
    
    for i, chapter in enumerate(chapters_data):
        print(f"  Creating {chapter['html_file']}...")
        
        # Build HTML
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(chapter['title'])}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
            background-color: #fff;
        }}
        
        .chapter-nav {{
            position: sticky;
            top: 0;
            background-color: #fff;
            border-bottom: 2px solid #ddd;
            padding: 15px 0;
            margin-bottom: 30px;
            z-index: 100;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        
        .nav-controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }}
        
        .nav-button {{
            padding: 10px 20px;
            background-color: #0066cc;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            border: none;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.2s;
        }}
        
        .nav-button:hover {{
            background-color: #0052a3;
        }}
        
        .nav-button:disabled {{
            background-color: #ccc;
            cursor: not-allowed;
        }}
        
        .chapter-select {{
            padding: 10px;
            font-size: 14px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background-color: white;
            cursor: pointer;
            flex-grow: 1;
            max-width: 400px;
        }}
        
        .chapter-title {{
            font-size: 2em;
            text-align: center;
            margin: 40px 0 30px 0;
            color: #1a1a1a;
        }}
        
        .chapter-content p {{
            margin: 1.2em 0;
            text-align: justify;
        }}
        
        @media (max-width: 600px) {{
            .nav-controls {{
                flex-direction: column;
            }}
            
            .chapter-select {{
                width: 100%;
                max-width: none;
            }}
        }}
        
        @media print {{
            .chapter-nav {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <nav class="chapter-nav">
        <div class="nav-controls">
"""
        
        # Previous button
        if i > 0:
            prev_chapter = chapters_data[i-1]
            html_content += f'            <a href="{prev_chapter["html_file"]}" class="nav-button">← Previous</a>\n'
        else:
            html_content += '            <button class="nav-button" disabled>← Previous</button>\n'
        
        # Dropdown
        html_content += '            <select class="chapter-select" onchange="if(this.value) window.location.href=this.value">\n'
        for idx, ch in enumerate(chapters_data):
            selected = ' selected' if idx == i else ''
            html_content += f'                <option value="{ch["html_file"]}"{selected}>{html.escape(ch["title"])}</option>\n'
        html_content += '            </select>\n'
        
        # Next button
        if i < len(chapters_data) - 1:
            next_chapter = chapters_data[i+1]
            html_content += f'            <a href="{next_chapter["html_file"]}" class="nav-button">Next →</a>\n'
        else:
            html_content += '            <button class="nav-button" disabled>Next →</button>\n'
        
        html_content += """        </div>
    </nav>
    
"""
        
        # Chapter content
        html_content += f'    <h1 class="chapter-title">{html.escape(chapter["title"])}</h1>\n'
        html_content += '    <div class="chapter-content">\n'
        
        # Split content into paragraphs
        paragraphs = chapter['content'].split('\n\n')
        for para in paragraphs:
            if para.strip():
                # Escape HTML and convert line breaks within paragraphs
                clean_para = html.escape(para.strip()).replace('\n', '<br>\n        ')
                html_content += f'        <p>{clean_para}</p>\n'
        
        html_content += """    </div>
</body>
</html>"""
        
        # Write HTML file
        output_file = output_path / chapter['html_file']
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        html_files_created.append(output_file)
    
    print(f"\n✓ Created {len(html_files_created)} HTML files in {output_path}")
    print(f"  Open {chapters_data[0]['html_file']} to start reading")
    return html_files_created


if __name__ == "__main__":
    import sys
    
    # Default to outputs/rekindling directory, or use command line argument
    if len(sys.argv) > 1:
        input_dir = sys.argv[1]
    else:
        input_dir = "../outputs/rekindling"
    
    # Optional: output subdirectory name (will be placed under public/)
    if len(sys.argv) > 2:
        output_subdir = sys.argv[2]
    else:
        output_subdir = None
    
    create_chapter_html_files(input_dir, output_subdir)
