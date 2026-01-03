#######
# Regendering Script for "John Shepard" to "Jane Shepard" #######
# This script identifies references to John Shepard in text files
# and generates passes the entire text through the LLM to alter Shepard's gender.
# 
# As of 2025-12-26, it's the best approach to ensure consistency and context-aware changes.
#
# USAGE:
#   From the project root directory:
#     python src/regender_v2.py [input_directory]
#
#   Examples:
#     python src/regender_v2.py                      # Uses default: inputs/adamo
#     python src/regender_v2.py inputs/rekindling    # Process rekindling chapters
#     python src/regender_v2.py inputs/custom        # Process custom directory
#
#   Output will be saved to outputs/{directory_name}/
#   Verification logs will be saved to outputs/verification_log/
####### 

from openai import OpenAI
import json
from pathlib import Path
import re
import os
import sys
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


TRANSLATION_PROMPT = """Transform this text to make the protagonist "John Shepard" female instead of male.

Read this text carefully. The protagonist is "John Shepard" - a Commander, Spectre, and war hero who is currently male but will be changed to female.

Your task: Identify EVERY reference to John Shepard in the text. This includes:
1. Direct: "Shepard", "Commander Shepard" (leave these unchanged - last name stays as-is)
2. First name: Any mentions of Shepard's first name "John" (will be changed to "Jane")
3. Pronouns: "he", "him", "his" when they refer to Shepard/John
4. Nouns: "man", "guy", "male" when describing Shepard/John. Also his status as "boyfriend" or "human". 
5. Indirect: "the Commander", "the Spectre", etc. when referring to Shepard/John

Based on the identified references to male John Shepard, generate precise edits to make Shepard female.


Changes to make:
1. Change male pronouns (he/him/his) to female (she/her/hers) when referring to Shepard
2. Change Shepard's first name to "Jane" (keep "Shepard" as-is)
3. Change gendered nouns when referring to Shepard: "man" → "woman", "guy" → "woman/person"
4. Remove or adapt masculine-only physical traits (e.g., beard)
5. Keep all other characters' genders unchanged - only Shepard becomes female

Rules:
- he/him/his (John Shepard) → she/her/hers
- "this man" (John Shepard) → "this woman"
- "the guy" (John Shepard) → "the woman" or "she"
- Shepard's first name John → "Jane"
- Designations like "boyfriend" → "girlfriend"
- DO NOT change "Shepard" or "Commander Shepard" - leave last name references unchanged
- Remove/adapt masculine-only traits (beard, etc.)

Sometimes the change creates repeated pronouns, for example: "Several minutes passed with them lying together, with her on top of her." (the original sentence was "Several minutes passed with them lying together, with her on top of him"). If you see such an example of repeated pronouns, please change the second pronoun to a more appropriate alternative (like a name or a noun - him refers to Shepard, her refers to Tali/the Quarian in this specific example). 

**CRITICAL RULES**:
- Return the COMPLETE text with all changes applied
- Preserve ALL formatting, whitespace, line breaks, and punctuation exactly
- Do NOT summarize, skip sections, or add commentary
- Do NOT change the plot, dialogue (except pronouns), or any content beyond gender changes
- Other male characters stay male - ONLY Shepard changes to female

Return ONLY the transformed text, nothing else."""

def translate_chapter(text):
    """Send entire chapter and get back translated version"""
    print("  Sending text for translation...")
    
    response = client.responses.create(
        model="gpt-4.1",  # Use full GPT-4.1 for longer context and better quality
        input=[
            {
                "role": "system",
                "content": (
                    "You are a precise text editor.\n"
                    "You transform text to change character genders while preserving everything else.\n"
                    "Return ONLY the complete transformed text with no additions or omissions."
                )
            },
            {
                "role": "user",
                "content": f"{TRANSLATION_PROMPT}\n\n{text}"
            }
        ],
        temperature=0
    )
    
    translated_text = response.output_text
    
    print(f"  Received {len(translated_text)} characters (original: {len(text)})")
    
    # Sanity check - warn if length changed dramatically
    length_ratio = len(translated_text) / len(text)
    if length_ratio < 0.9 or length_ratio > 1.1:
        print(f"    ⚠️  WARNING: Length changed by {(length_ratio - 1) * 100:.1f}%")
    
    return translated_text

def translate_chapter_chunked(text, chunk_size=12000):
    """Translate long chapters in overlapping chunks"""
    
    if len(text) < chunk_size:
        return translate_chapter(text)
    
    print(f"  Chapter is long ({len(text)} chars), using chunked approach...")
    
    # Split into paragraphs
    paragraphs = text.split('\n\n')
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for para in paragraphs:
        para_length = len(para)
        
        if current_length + para_length > chunk_size and current_chunk:
            # Save current chunk
            chunks.append('\n\n'.join(current_chunk))
            # Start new chunk with overlap (last 2 paragraphs)
            current_chunk = current_chunk[-2:] if len(current_chunk) > 2 else []
            current_length = sum(len(p) for p in current_chunk)
        
        current_chunk.append(para)
        current_length += para_length
    
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    print(f"  Split into {len(chunks)} chunks")
    
    # Translate each chunk
    translated_chunks = []
    
    for idx, chunk in enumerate(chunks):
        print(f"  Translating chunk {idx + 1}/{len(chunks)}...")
        translated = translate_chapter(chunk)
        translated_chunks.append(translated)
    
    # Merge chunks (remove overlapping parts)
    # This is approximate - just take first chunk fully, then append rest
    result = translated_chunks[0]
    
    for i in range(1, len(translated_chunks)):
        # Skip the overlapping paragraphs (rough heuristic)
        chunk_paras = translated_chunks[i].split('\n\n')
        result += '\n\n' + '\n\n'.join(chunk_paras[2:])
    
    return result

def verify_translation(original, translated):
    """Quick verification checks"""
    issues = []
    
    # Check for common problems
    if len(translated) < len(original) * 0.8:
        issues.append("Text appears truncated")
    
    if "..." in translated and "..." not in original:
        issues.append("May contain ellipsis indicating skipped content")
    
    # Count Shepard mentions (should be roughly the same)
    orig_shepard_count = original.lower().count("shepard")
    trans_shepard_count = translated.lower().count("shepard")
    
    if abs(orig_shepard_count - trans_shepard_count) > 2:
        issues.append(f"Shepard mention count changed: {orig_shepard_count} → {trans_shepard_count}")
    
    # Check for leftover male pronouns near Shepard
    shepard_contexts = re.finditer(r'Shepard[^.!?]{0,100}?\b(he|him|his)\b', translated, re.IGNORECASE)
    male_pronouns_near_shepard = list(shepard_contexts)
    
    if male_pronouns_near_shepard:
        issues.append(f"Found {len(male_pronouns_near_shepard)} potential male pronouns near Shepard")
    
    return issues

if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1:
        input_dir = Path(sys.argv[1])
    else:
        input_dir = Path("inputs/adamo")
    
    # Derive output directory from input directory name
    input_name = input_dir.name
    output_dir = Path("outputs") / input_name
    verification_dir = Path("outputs/verification_log")
    
    # Create directories
    output_dir.mkdir(exist_ok=True, parents=True)
    verification_dir.mkdir(exist_ok=True, parents=True)
    
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Verification logs: {verification_dir}")
    
    chapter_files = sorted(input_dir.glob("*.txt"))

    for i, chapter_file in enumerate(chapter_files, 1):
        print(f"\n{'='*60}")
        print(f"Processing {chapter_file.name} ({i}/{len(chapter_files)})")
        print('='*60)
        
        with open(chapter_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Check if chapter is too long for context window
        # GPT-4.1 has 128k context, roughly 100k tokens
        # Estimate ~4 chars per token
        estimated_tokens = len(text) / 4
        
        if estimated_tokens > 90000:  # Leave room for prompt + response
            print(f"  ⚠️  Chapter may be too long ({estimated_tokens:.0f} estimated tokens)")
            print(f"  Consider splitting this chapter or using a chunked approach")
            continue
        
        # Translate
        translated_text = translate_chapter_chunked(text)
        
        # Verify
        print("  Verifying translation...")
        issues = verify_translation(text, translated_text)
        
        if issues:
            print("  ⚠️  Verification issues found:")
            for issue in issues:
                print(f"    - {issue}")
            
            # Save verification report
            with open(verification_dir / f"{chapter_file.stem}_issues.json", 'w') as f:
                json.dump(issues, f, indent=2)
        else:
            print("  ✓ Verification passed")
        
        # Save result
        output_file = output_dir / chapter_file.name
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(translated_text)
        
        print(f"✓ Saved to {output_file}")

    print(f"\n{'='*60}")
    print(f"Done! Processed {len(chapter_files)} chapters.")
    print(f"Check '{verification_dir}/' for any issues")
    print('='*60)
