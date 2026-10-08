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
    
    # Determine output directory: docs/{output_subdir or input_dir_name}/
    if output_subdir is None:
        output_subdir = input_path.name
    
    output_path = Path("docs") / output_subdir
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
        
        # Back to the story's table of contents
        html_content += '            <a href="index.html" class="nav-button">Contents</a>\n'

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
    return chapters_data


# Shared look for the index pages, matching the chapter pages
INDEX_STYLE = """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
            background-color: #fff;
        }

        h1 {
            font-size: 2em;
            text-align: center;
            margin: 40px 0 10px 0;
            color: #1a1a1a;
        }

        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
        }

        .back {
            color: #0066cc;
            text-decoration: none;
            font-size: 14px;
        }

        .entries {
            list-style: none;
            padding: 0;
            border-top: 1px solid #ddd;
        }

        .entries li {
            border-bottom: 1px solid #ddd;
        }

        .entries a {
            display: flex;
            justify-content: space-between;
            gap: 15px;
            padding: 14px 4px;
            color: #0066cc;
            text-decoration: none;
        }

        .entries a:hover {
            background-color: #f5f5f5;
        }

        .entries .meta {
            color: #666;
            white-space: nowrap;
        }
"""


def index_page(title, body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>{INDEX_STYLE}    </style>
</head>
<body>
{body}
</body>
</html>"""


def create_story_index(output_path, title, chapters_data):
    """docs/{story}/index.html: the story's table of contents, served when no chapter is in the URL."""
    items = "\n".join(
        f'        <li><a href="{ch["html_file"]}"><span>{html.escape(ch["title"])}</span>'
        f'<span class="meta">{len(ch["content"].split()):,} words</span></a></li>'
        for ch in chapters_data
    )
    words = sum(len(ch["content"].split()) for ch in chapters_data)
    body = f"""    <a class="back" href="../index.html">← All stories</a>
    <h1>{html.escape(title)}</h1>
    <p class="subtitle" data-chapters="{len(chapters_data)}" data-words="{words}">{len(chapters_data)} chapters · {words:,} words</p>
    <ol class="entries">
{items}
    </ol>"""
    (output_path / "index.html").write_text(index_page(title, body), encoding="utf-8")
    print(f"✓ Created {output_path / 'index.html'} (table of contents)")


def create_site_index(docs_path=Path("docs")):
    """docs/index.html: links to every story that has a table of contents."""
    stories = []
    for story_index in sorted(docs_path.glob("*/index.html")):
        page = story_index.read_text(encoding="utf-8")
        title = html.unescape(re.search(r"<title>(.*?)</title>", page).group(1))
        meta = re.search(r'data-chapters="(\d+)" data-words="(\d+)"', page)
        stories.append((story_index.parent.name, title, int(meta.group(1)), int(meta.group(2))))
    items = "\n".join(
        f'        <li><a href="{name}/index.html"><span>{html.escape(title)}</span>'
        f'<span class="meta">{chapters} chapters · {words:,} words</span></a></li>'
        for name, title, chapters, words in stories
    )
    body = f"""    <h1>Stories</h1>
    <p class="subtitle">{len(stories)} {'story' if len(stories) == 1 else 'stories'}</p>
    <ul class="entries">
{items}
    </ul>"""
    (docs_path / "index.html").write_text(index_page("Stories", body), encoding="utf-8")
    print(f"✓ Created {docs_path / 'index.html'} ({len(stories)} stories)")


def story_title(output_path, title):
    """Explicit title, else the one already on the story's index page, else the folder name."""
    if title:
        return title
    existing = output_path / "index.html"
    if existing.exists():
        return html.unescape(re.search(r"<title>(.*?)</title>", existing.read_text(encoding="utf-8")).group(1))
    return output_path.name.replace("_", " ").title()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build web pages for a story's chapter txt files")
    parser.add_argument("input_dir", nargs="?", default="outputs/rekindling")
    parser.add_argument("output_subdir", nargs="?", help="folder under docs/ (default: input folder name)")
    parser.add_argument("--title", help="story title for the index pages (remembered for later runs)")
    args = parser.parse_args()

    output_path = Path("docs") / (args.output_subdir or Path(args.input_dir).name)
    title = story_title(output_path, args.title)
    chapters = create_chapter_html_files(args.input_dir, args.output_subdir)
    if chapters:
        create_story_index(output_path, title, chapters)
        create_site_index()
