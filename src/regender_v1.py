#######
# Regendering Script for "John Shepard" to "Jane Shepard" #######
# This script identifies references to John Shepard in text files
# and generates edits at specific locations to change Shepard's gender. 
# 
# As of 2025-12-26, it doesn't quite work. 
#
# USAGE:
#   From the project root directory:
#     python src/regender_v1.py [input_directory]
#
#   Examples:
#     python src/regender_v1.py                    # Uses default: inputs/rekindling
#     python src/regender_v1.py inputs/adamo       # Process adamo chapters
#     python src/regender_v1.py inputs/custom      # Process custom directory
#
#   Output will be saved to outputs/{directory_name}/
#   Analysis logs will be saved to outputs/analysis_log/
####### 

from openai import OpenAI
import json
from pathlib import Path
import unicodedata
import re
import os
import sys
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1:
        input_dir = Path(sys.argv[1])
    else:
        input_dir = Path("inputs/rekindling")
    
    # Derive output directory from input directory name
    input_name = input_dir.name
    output_dir = Path("outputs") / input_name
    analysis_dir = Path("outputs/analysis_log")
    
    # Create directories
    output_dir.mkdir(exist_ok=True, parents=True)
    analysis_dir.mkdir(exist_ok=True, parents=True)
    
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Analysis logs: {analysis_dir}")
    
    chapter_files = sorted(input_dir.glob("*.txt"))

# Stage 1: Identify all Shepard references
IDENTIFICATION_PROMPT = """Read this text carefully. The protagonist is "John Shepard" - a Commander, Spectre, and war hero who is currently male but will be changed to female.

Your task: Identify EVERY reference to John Shepard in the text. This includes:
1. Direct: "Shepard", "Commander Shepard" (leave these unchanged - last name stays as-is)
2. First name: Any mentions of Shepard's first name "John" (will be changed to "Jane")
3. Pronouns: "he", "him", "his" when they refer to Shepard/John
4. Nouns: "man", "guy", "male" when describing Shepard/John. Also his status as "boyfriend" or "human". 
5. Indirect: "the Commander", "the Spectre", etc. when referring to Shepard/John

**CRITICAL**: Pay close attention to pronoun referents. In passages with multiple characters:
- Track which "he/him/his" refers to Shepard vs other characters
- Pronouns after John Shepard's dialogue typically refer to Shepard
- Use narrative context and proximity to determine referents

For each reference, provide:
1. The phrase with surrounding context (10-20 words on each side)
2. The specific word(s) that refer to Shepard
3. Your confidence this refers to Shepard (high/medium/low)

Return as JSON array:
[
  {
    "context": "longer phrase with context",
    "reference": "the specific word(s)",
    "confidence": "high/medium/low",
    "explanation": "why this refers to Shepard"
  }
]

Return ONLY valid JSON, no other text."""

# Stage 2: Generate edits
EDIT_GENERATION_PROMPT = """Based on the identified references to male John Shepard, generate precise edits to make Shepard female.

**CRITICAL**: 
- You MUST generate exactly ONE edit for EVERY reference provided
- **DO NOT create overlapping edits** - if two references are in the same sentence/passage, create ONE edit that covers both
- If reference N is contained within reference N+1, SKIP reference N and only edit reference N+1
- Use STRAIGHT quotes (") not curly quotes (" ")
- Use three dots (...) not ellipsis (…)

Example of what NOT to do:
Reference 0: "A man feels the name"
Reference 1: "A man feels the name wash over him. He hears..."
BAD: Create separate edits for both (they overlap!)
GOOD: Create ONE edit for reference 1 (it contains reference 0)

For each reference (in the same order as provided), create an edit with:
- "reference_index": the index number from the input list (0, 1, 2, etc.)
- "original": unique phrase to find (include enough context to be unique, 15-30 words)
- "replacement": the corrected version
- "reason": brief explanation

Rules:
- he/him/his (John Shepard) → she/her/hers
- "this man" (John Shepard) → "this woman"
- "the guy" (John Shepard) → "the woman" or "she"
- Shepard's first name John → "Jane"
- Designations like "boyfriend" → "girlfriend"
- DO NOT change "Shepard" or "Commander Shepard" - leave last name references unchanged
- Remove/adapt masculine-only traits (beard, etc.)

**IMPORTANT**: 
- Generate edits for ALL {num_refs} references provided
- Use the "context" field from each reference to construct your "original" text
- Include enough surrounding words to make each edit unique in the document
- If a reference seems unclear, still generate an edit based on the context provided

Return ONLY valid JSON array with exactly {num_refs} edits, no other text."""

# Add this new stage between identification and edit generation

DISAMBIGUATION_PROMPT = """You have identified references to Shepard in this text. However, some passages contain multiple male characters, which creates ambiguity.

Your task: For each identified reference with "medium" or "low" confidence, perform careful disambiguation.

For the following text and identified references, determine:
1. Is this reference actually to Shepard, or to another character?
2. What clues in the surrounding context help determine this?
3. Should this reference be included in edits (high confidence) or excluded (refers to someone else)?

Pay special attention to:
- Pronouns that appear far from Shepard's name
- Scenes with multiple male characters
- Subject-verb agreement and sentence structure
- Logical flow of who is performing actions
- The romantic context (is Shepard the boyfriend/girlfriend mentioned?)

For each reference, return:
{
  "original_reference": "the identified reference",
  "context": "the surrounding text",
  "refers_to_shepard": true/false,
  "reasoning": "explanation of your determination",
  "confidence": "high/medium/low"
}

Return ONLY valid JSON array."""

def stage1_5_disambiguate(text, references):
    """Stage 1.5: Disambiguate tricky references"""
    print("  Stage 1.5: Disambiguating references...")
    
    # Only disambiguate medium/low confidence ones
    to_disambiguate = [r for r in references if r['confidence'] in ['medium', 'low']]
    
    if not to_disambiguate:
        print("    No ambiguous references to check")
        return references
    
    print(f"    Checking {len(to_disambiguate)} ambiguous references...")
    
    refs_summary = json.dumps(to_disambiguate, indent=2)
    
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": (
                    "You are an expert at pronoun disambiguation.\n"
                    "Return ONLY valid JSON.\n"
                    "Do not include markdown, code fences, or explanations."
                )
            },
            {
                "role": "user",
                "content": f"{DISAMBIGUATION_PROMPT}\n\nReferences to check:\n{refs_summary}\n\nOriginal text:\n{text}"
            }
        ],
        temperature=0
    )
    
    output = response.output_text.strip()
    if output.startswith("```"):
        output = output.split("\n", 1)[1].rsplit("\n", 1)[0]
    
    disambiguated = json.loads(output)
    
    # Update original references with disambiguation results
    high_conf_refs = [r for r in references if r['confidence'] == 'high']
    
    for d in disambiguated:
        if d['refers_to_shepard']:
            high_conf_refs.append({
                'context': d['context'],
                'reference': d['original_reference'],
                'confidence': d['confidence'],
                'explanation': d['reasoning']
            })
    
    print(f"    Confirmed {len(high_conf_refs)} total references")
    return high_conf_refs

def stage1_identify_references(text):
    """Stage 1: Identify all references to Shepard"""
    print("  Stage 1: Identifying Shepard references...")
    
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": (
                    "You are a precise text analyzer.\n"
                    "Return ONLY valid JSON.\n"
                    "Do not include markdown, code fences, or explanations."
                )
            },
            {
                "role": "user",
                "content": f"{IDENTIFICATION_PROMPT}\n\nText:\n{text}"
            }
        ],
        temperature=0
    )
    
    output = response.output_text.strip()
    
    # Defensive cleanup (rare, but safe)
    if output.startswith("```"):
        output = output.split("\n", 1)[1].rsplit("\n", 1)[0]
    
    references = json.loads(output)
    print(f"    Found {len(references)} references")
    
    # Filter to high/medium confidence
    filtered = [r for r in references if r['confidence'] in ['high', 'medium']]
    print(f"    {len(filtered)} are high/medium confidence")
    
    return filtered

def stage2_generate_edits(text, references):
    """Stage 2: Generate specific edits based on identified references"""
    print("  Stage 2: Generating edits...")
    
    num_refs = len(references)
    references_summary = json.dumps(references, indent=2)
    
    # Add index to each reference for tracking
    indexed_refs = [
        {**ref, "index": i} 
        for i, ref in enumerate(references)
    ]
    
    prompt = EDIT_GENERATION_PROMPT.format(num_refs=num_refs)
    
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": (
                    "You are a precise text editor.\n"
                    "Return ONLY valid JSON.\n"
                    "Do not include markdown, code fences, or explanations.\n"
                    f"You MUST generate exactly {num_refs} edits."
                )
            },
            {
                "role": "user",
                "content": f"{prompt}\n\nIdentified references:\n{json.dumps(indexed_refs, indent=2)}\n\nOriginal text:\n{text}"
            }
        ],
        temperature=0
    )
    
    output = response.output_text.strip()
    
    if output.startswith("```"):
        output = output.split("\n", 1)[1].rsplit("\n", 1)[0]
    
    edits = json.loads(output)
    
    # Verify we got the right number
    if len(edits) != num_refs:
        print(f"    ⚠️  WARNING: Expected {num_refs} edits, got {len(edits)}")
        print(f"    Missing edits for references: {set(range(num_refs)) - {e.get('reference_index', -1) for e in edits}}")
    else:
        print(f"    ✓ Generated all {len(edits)} edits")
    
    return edits


def normalize_text(text):
    """Normalize unicode characters, whitespace, and newlines for matching"""
    # Normalize unicode (NFC form)
    text = unicodedata.normalize('NFC', text)
    
    # Replace common unicode variants with ASCII equivalents
    replacements = {
        '\u201c': '"',  # Left double quote
        '\u201d': '"',  # Right double quote
        '\u2018': "'",  # Left single quote
        '\u2019': "'",  # Right single quote
        '\u2026': '...',  # Ellipsis
        '\u2013': '-',  # En dash
        '\u2014': '--', # Em dash
        '\xa0': ' ',    # Non-breaking space
        '\u202f': ' ',  # Narrow no-break space
        '\u2009': ' ',  # Thin space
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text

def normalize_whitespace(text):
    """Normalize all whitespace to single spaces, preserve structure"""
    # Replace all whitespace (spaces, tabs, newlines) with single space
    # But keep paragraph breaks (multiple newlines) as single newline
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs -> single space
    text = re.sub(r'\n\n+', '\n\n', text)  # Multiple newlines -> double newline
    return text.strip()

def apply_edits_robust(text, edits):
    """Apply edits with normalization, flexible whitespace matching, and overlap handling"""
    applied = 0
    skipped = 0
    failed_edits = []
    
    # First pass: Find all match positions without applying
    edit_positions = []
    normalized_text = normalize_text(text)
    
    for idx, edit in enumerate(edits):
        original = edit["original"]
        normalized_original = normalize_text(original)
        ref_idx = edit.get('reference_index', idx)
        
        position = find_match_position(text, normalized_text, normalized_original)
        
        if position is not None:
            edit_positions.append({
                'index': idx,
                'position': position['start'],
                'end': position['end'],
                'edit': edit,
                'ref_idx': ref_idx
            })
        else:
            print(f"    ⚠️  Failed to match (ref {ref_idx}): '{original[:50]}...'")
            failed_edits.append({
                'reference_index': ref_idx,
                'original': original,
                'replacement': edit['replacement'],
                'reason': edit.get('reason', 'unknown')
            })
            skipped += 1
    
    # Sort by position (REVERSE order so we apply from end to start)
    # This prevents position shifts from affecting later edits
    edit_positions.sort(key=lambda x: x['position'], reverse=True)
    
    # Check for overlaps
    for i in range(len(edit_positions) - 1):
        current = edit_positions[i]
        next_edit = edit_positions[i + 1]
        
        if current['position'] < next_edit['end']:
            print(f"    ⚠️  Overlap detected between ref {current['ref_idx']} and {next_edit['ref_idx']}")
            # Keep the earlier one (lower ref_idx), skip the later one
            if current['ref_idx'] > next_edit['ref_idx']:
                failed_edits.append({
                    'reference_index': current['ref_idx'],
                    'original': current['edit']['original'],
                    'replacement': current['edit']['replacement'],
                    'reason': f"Overlaps with edit {next_edit['ref_idx']}"
                })
                edit_positions[i] = None
                skipped += 1
            else:
                failed_edits.append({
                    'reference_index': next_edit['ref_idx'],
                    'original': next_edit['edit']['original'],
                    'replacement': next_edit['edit']['replacement'],
                    'reason': f"Overlaps with edit {current['ref_idx']}"
                })
                edit_positions[i + 1] = None
                skipped += 1
    
    # Remove skipped edits
    edit_positions = [e for e in edit_positions if e is not None]
    
    # Apply edits from end to start (so positions don't shift)
    for edit_pos in edit_positions:
        edit = edit_pos['edit']
        start = edit_pos['position']
        end = edit_pos['end']
        
        normalized_replacement = normalize_text(edit['replacement'])
        
        text = text[:start] + normalized_replacement + text[end:]
        applied += 1
    
    print(f"    Applied {applied} edits, skipped {skipped}")
    
    return text, failed_edits

def find_match_position(text, normalized_text, normalized_original):
    """Find match position using various strategies, return start/end positions"""
    
    # Try 1: Exact match on normalized text
    if normalized_text.count(normalized_original) == 1:
        pos = normalized_text.find(normalized_original)
        return {'start': pos, 'end': pos + len(normalized_original)}
    
    # Try 2: Whitespace-flexible matching
    original_ws_norm = normalize_whitespace(normalized_original)
    pattern_parts = re.escape(original_ws_norm).split(r'\ ')
    pattern = r'\s+'.join(pattern_parts)
    
    matches = list(re.finditer(pattern, normalized_text, re.DOTALL))
    
    if len(matches) == 1:
        match = matches[0]
        return {'start': match.start(), 'end': match.end()}
    
    # Try 3: Line-break agnostic (more complex, similar to before)
    original_no_newlines = re.sub(r'\s+', ' ', normalized_original)
    text_no_newlines = re.sub(r'\s+', ' ', normalized_text)
    
    if text_no_newlines.count(original_no_newlines) == 1:
        # Find approximate position
        approx_pos = text_no_newlines.find(original_no_newlines)
        
        # Map back to real position (accounting for whitespace differences)
        real_start = map_position_with_whitespace(normalized_text, text_no_newlines, approx_pos)
        real_end = real_start + len(normalized_original)
        
        return {'start': real_start, 'end': real_end}
    
    return None

def map_position_with_whitespace(original_text, collapsed_text, collapsed_pos):
    """Map position in whitespace-collapsed text back to original text"""
    orig_idx = 0
    collapsed_idx = 0
    
    while collapsed_idx < collapsed_pos and orig_idx < len(original_text):
        if original_text[orig_idx].isspace():
            # Skip whitespace in original, it's collapsed in the other
            if collapsed_idx < len(collapsed_text) and collapsed_text[collapsed_idx] == ' ':
                collapsed_idx += 1
            orig_idx += 1
        else:
            orig_idx += 1
            collapsed_idx += 1
    
    return orig_idx

    for i, chapter_file in enumerate(chapter_files, 1):
        if i == 1:
            continue
        print(f"\n{'='*60}")
        print(f"Processing {chapter_file.name} ({i}/{len(chapter_files)})")
        print('='*60)
        
        with open(chapter_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Stage 1: Identify references
        references = stage1_identify_references(text)
        
        # Save references for review
        with open(analysis_dir / f"{chapter_file.stem}_references.json", 'w') as f:
            json.dump(references, f, indent=2)
        
        # Stage 2: Generate edits
        edits = stage2_generate_edits(text, references)
        
        # Save edits for review
        with open(analysis_dir / f"{chapter_file.stem}_edits.json", 'w') as f:
            json.dump(edits, f, indent=2)

        with open(analysis_dir / f"{chapter_file.stem}_edits.json", 'r') as f:
            edits = json.load(f)
        
        # Apply edits with robust matching
        print("  Applying edits...")
        edited_text, failed_edits = apply_edits_robust(text, edits)
        
        # Save failed edits if any
        if failed_edits:
            with open(analysis_dir / f"{chapter_file.stem}_failed_edits.json", 'w') as f:
                json.dump(failed_edits, f, indent=2)
        
        # Save result
        output_file = output_dir / chapter_file.name
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(edited_text)
        
        print(f"✓ Saved to {output_file}")

    print(f"\n{'='*60}")
    print(f"Done! Processed {len(chapter_files)} chapters.")
    print(f"Review analysis files in '{analysis_dir}/' for any failed edits")
    print('='*60)