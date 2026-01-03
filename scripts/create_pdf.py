#######
# Export script 
# This script takes in a directory of text files representing chapters
# and generates a single PDF for all of them
# 
# As of 2025-12-26, it works fine
####### 

from pathlib import Path
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER


def natural_sort_key(path):
    """Extract numbers from filename for natural sorting"""
    filename = path.name
    # Extract all numbers from the filename
    numbers = re.findall(r'\d+', filename)
    if numbers:
        return int(numbers[0])
    return 0


def create_pdf_from_chapters(input_dir, pdf_filename="compiled_chapters.pdf"):
    """Create a single PDF from all text files in input_dir"""
    print(f"\n{'='*60}")
    print(f"Creating PDF from chapters in {input_dir}")
    print('='*60)
    
    input_path = Path(input_dir)
    
    # Get all text files sorted naturally (ch1, ch2, ..., ch10, ch11, ch12)
    chapter_files = sorted(input_path.glob("*.txt"), key=natural_sort_key)
    
    if not chapter_files:
        print("  ⚠️  No text files found in input directory")
        return None
    
    # Create PDF
    pdf_path = input_path / pdf_filename
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Chapter title style (larger, centered)
    title_style = ParagraphStyle(
        'ChapterTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=20,
        spaceBefore=10
    )
    
    # Body text style
    body_style = styles['BodyText']
    body_style.fontSize = 11
    body_style.leading = 14
    body_style.spaceAfter = 10
    
    # Build PDF content
    story = []
    
    for i, chapter_file in enumerate(chapter_files):
        print(f"  Adding {chapter_file.name} to PDF...")
        
        with open(chapter_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            continue
        
        # First line is the title
        title = lines[0].strip()
        content = ''.join(lines[1:]).strip()
        
        # Add title
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Add content paragraphs
        paragraphs = content.split('\n\n')
        for para in paragraphs:
            if para.strip():
                # Clean up the text for reportlab (escape special chars)
                clean_para = para.strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(clean_para, body_style))
        
        # Add page break after each chapter (except last)
        if i < len(chapter_files) - 1:
            story.append(PageBreak())
    
    # Build PDF
    print(f"  Building PDF...")
    doc.build(story)
    
    print(f"✓ PDF created: {pdf_path}")
    print(f"  Total chapters: {len(chapter_files)}")
    return pdf_path


if __name__ == "__main__":
    import sys
    
    # Default to outputs/rekindling directory, or use command line argument
    if len(sys.argv) > 1:
        input_dir = sys.argv[1]
    else:
        input_dir = "outputs/rekindling"
    
    # Optional: custom PDF filename
    if len(sys.argv) > 2:
        pdf_filename = sys.argv[2]
    else:
        pdf_filename = "compiled_chapters.pdf"
    
    create_pdf_from_chapters(input_dir, pdf_filename)
