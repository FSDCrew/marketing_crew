from pathlib import Path
import os, shutil
import textwrap
import pypandoc
from crewai.tools import tool
from typing import Optional, Sequence

def _ensure_pandoc_env() -> None:
    """Ensure PYPANDOC_PANDOC points to a pandoc executable, downloading if needed."""
    if shutil.which("pandoc"):
        return
    downloaded = pypandoc.download_pandoc()
    if not downloaded:
        return
    p = Path(downloaded)
    pandoc_path = p if p.is_file() else p / ("pandoc.exe" if os.name == "nt" else "pandoc")
    os.environ["PYPANDOC_PANDOC"] = str(pandoc_path)

def _safe_mkdirs(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)

@tool("Markdown to Word Doc")
def markdown_to_word_doc(
    markdown: str,
    # output_path: str | None = None,
) -> dict:
    """
    Convert Markdown string to a Word (.docx) using Pandoc, preserving Markdown features.

    - Uses GitHub-Flavored Markdown (GFM) with common extensions:
      tables, task lists, strikethrough, footnotes, $...$ math, smart quotes.
    - Optionally map styles via a Word template (reference_docx).
    - Optionally set resource_path so relative images are embedded properly.
    """
    # output_path = output_path or "./output/markdown_to_word.docx"
    output_path = "./output/markdown_to_word.docx"
    if not markdown or not markdown.strip():
        return {
            "status": "error",
            "output_format": "docx",
            "output_path": output_path,
            "notes": "Markdown input is empty.",
            "raw": ""
        }

    if not output_path.lower().endswith(".docx"):
        return {
            "status": "error",
            "output_format": "docx",
            "output_path": output_path,
            "notes": "output_path must end with .docx (Pandoc targets .docx, not legacy .doc).",
            "raw": ""
        }

    _ensure_pandoc_env()
    _safe_mkdirs(output_path)
    
    markdown = textwrap.dedent(markdown).lstrip("\ufeff").lstrip("\n")
    frmt = "gfm+smart+pipe_tables+strikeout+task_lists+tex_math_dollars+footnotes"

    try:
        pypandoc.convert_text(
            markdown,
            to="docx",
            format=frmt,
            outputfile=output_path,
        )
        return {
            "status": "success",
            "output_format": "docx",
            "output_path": output_path,
            "notes": (
                "Converted with Pandoc using GFM extensions. "
                "If styles look off, provide a reference .docx to control Word styles."
            ),
            "raw": ""
        }
    except Exception as e:
        return {
            "status": "error",
            "output_format": "docx",
            "output_path": output_path,
            "notes": "Unexpected error during conversion.",
            "raw": repr(e)
        }

if __name__ == "__main__":
    markdown = """# Market Research Report for SMU Patron's Day 2026 Marketing Campaign

## Executive Summary
This report analyzes the competitive landscape and emerging trends related to "SMU Patron's Day 2026" within Singapore's university campus festival scene, focusing on Instagram content strategies and audience engagement. The key competitors identified include SMU Arts Fest 2025 and NTU Fest 2025. Insights from their Instagram activities reveal effective content types, visual styles, and engagement tactics that align well with the target audience of SMU students, alumni, and the broader Singapore public who enjoy immersive campus festivals and community celebrations. Recommendations are provided to optimize SMU Patron's Day 2026 content strategy for maximum impact.

## Competitive Landscape
- **SMU Patron's Day**: An annual free event held at SMU Campus Green featuring entertainment, food villages, games (like PD Bingo), and interactive experiences (e.g., SMU Makers). Instagram content is community-centric, highlighting event announcements, behind-the-scenes of organizing committees, performance recaps, and carnival activities. Visuals are vibrant, mixing professional and candid shots. Hashtags: #SMUPD, #SGSMULIFE, #SGSMU25.
- **SMU Arts Fest 2025**: A large-scale arts festival celebrating SMU's 25th and SG's 60th anniversaries, featuring music, dance, theatre, and visual arts. Instagram posts emphasize youth talent, university collaboration, cultural storytelling, and artistic creativity. Visual style is artistic and immersive, with frequent event updates and lineup reveals. Hashtags: #SMUArtsFest2025, #SGSMU, #SGSMULife.
- **NTU Fest 2025**: NTU's largest campus party focusing on music, games, giveaways, and social connection. Instagram content is energetic and youthful, showcasing organizing teams, sponsor engagement, live performances, and community vibes. Hashtags: #NTUFest2025, #NTUSU, #NTUSG.

## Emerging Trends
- **Community and Behind-the-Scenes Content**: Transparency and showcasing the organizing teams build trust and anticipation.
- **User-Generated and Student/Alumni-Centric Stories**: Highlighting real experiences and creativity fosters stronger community bonds.
- **Multi-format Visual Content**: Use of professional photos, candid shots, videos, and reels increases engagement.
- **Event Countdown and Interactive Campaigns**: Bingo games, giveaways, and challenges encourage active participation.
- **Cross-University Collaboration and Inclusion**: Seen in SMU Arts Fest, this increases reach and diversity of content.
- **Consistent Hashtag Usage**: Campaign-specific and community hashtags amplify organic reach.

## Successful Examples/References
- SMU Patron's Day Instagram (@smupatronsday) effectively uses event promo posts, committee highlights, and engaging visuals with clear calls to action.
- SMU Arts Fest (@smuartsfest) excels in storytelling through artistic and cultural showcases and collaborations, with frequent updates during the festival period.
- NTU Fest (@ntufest) leverages giveaways, sponsor shoutouts, and vibrant event recaps, maintaining high audience engagement.

## Recommendations for SMU Patron's Day 2026
1. **Content Mix**: Combine professional event highlights, behind-the-scenes footage, and authentic student/alumni stories.
2. **Interactive Elements**: Expand on PD Bingo and introduce digital challenges or filters to deepen engagement.
3. **Visual Storytelling**: Use vibrant, youthful, and diverse visuals reflecting the campus culture and student life.
4. **Consistent Posting Schedule**: Increase frequency leading up to the event and maintain momentum during and after.
5. **Cross-Promotion**: Collaborate with other university festivals and student groups for wider reach.
6. **Hashtag Strategy**: Continue using branded hashtags (#SMUPD, #SGSMULIFE, #SGSMU25) and introduce event-specific tags for 2026.
7. **Leverage Alumni Networks**: Feature alumni success stories and their Patron's Day participation to bridge generations.
8. **Sustainability and Inclusivity**: Highlight eco-friendly initiatives and diverse cultural representation aligning with contemporary values.

## References
- SMU Patron's Day Official Website: https://patronsday.smu.edu.sg/
- Instagram Posts from SMU Patron's Day 2025: 
- https://www.instagram.com/p/DEhnutaoBgH/ (@sgsmu)
- https://www.instagram.com/p/DDrXwgnzJZ6/ (@smupatronsday)
- Instagram Posts from SMU Arts Fest 2025:
- https://www.instagram.com/p/DNnE90pym2g/ (@smuartsfest)
- https://www.instagram.com/p/DODj1sqDlAO/ (@sgsmu)
- Instagram Posts from NTU Fest 2025:
- https://www.instagram.com/p/DNLe24lzW81/ (@ntufest)
- https://www.instagram.com/p/DNIAebaBXuf/ (@ntu.su)

This comprehensive analysis should guide the content strategy for SMU Patron's Day 2026 to create a vibrant, engaging, and community-focused campaign that resonates strongly with the target audience and stands out in Singapore's university festival landscape.
"""
    print(markdown_to_word_doc.func(markdown=markdown, output_path="./output/social_media_schedule.docx"))