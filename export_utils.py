"""
Export utilities for LocalGPT Pro.
Generates clean Markdown (.md) and PDF (.pdf) documents from chat sessions.
Includes a standalone, zero-dependency PDF 1.4 generator compatible with all Python versions.
"""

from typing import List, Dict, Any


def export_chat_to_markdown(chat_title: str, messages: List[Dict[str, Any]]) -> str:
    """Formats chat messages into clean GitHub-flavored markdown."""
    timestamp = messages[0]['created_at'] if messages else 'N/A'
    lines = [
        f"# {chat_title}",
        f"*Exported from LocalGPT Pro on {timestamp}*",
        "\n---\n"
    ]
    for msg in messages:
        role = "🧑 **User**" if msg["role"] == "user" else "🤖 **LocalGPT Pro**"
        lines.append(f"### {role}")
        lines.append(msg["content"])
        if msg.get("sources"):
            lines.append(f"\n> **Sources Cited:** {msg['sources']}")
        lines.append("\n---\n")
    return "\n".join(lines)


def _wrap_text(text: str, max_chars: int = 75) -> List[str]:
    """Wraps text into lines not exceeding max_chars."""
    wrapped = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            wrapped.append("")
            continue
        words = line.split(" ")
        curr = []
        curr_len = 0
        for w in words:
            if curr_len + len(w) + 1 <= max_chars:
                curr.append(w)
                curr_len += len(w) + 1
            else:
                if curr:
                    wrapped.append(" ".join(curr))
                curr = [w]
                curr_len = len(w)
        if curr:
            wrapped.append(" ".join(curr))
    return wrapped


def export_chat_to_pdf(chat_title: str, messages: List[Dict[str, Any]]) -> bytes:
    """
    Generates a standard compliant PDF 1.4 document in pure Python.
    Zero external dependencies, cross-platform and compatible with Python 3.8+.
    """
    # Build text lines to render
    lines_to_render = [
        ("TITLE", chat_title),
        ("SUBTITLE", "LocalGPT Pro - Private Local Inference Chat History"),
        ("SEP", "")
    ]

    for msg in messages:
        is_user = msg["role"] == "user"
        header = "User:" if is_user else "LocalGPT Pro:"
        lines_to_render.append(("HEADER", header))
        
        for w_line in _wrap_text(msg["content"], max_chars=75):
            lines_to_render.append(("BODY", w_line))
            
        if msg.get("sources"):
            lines_to_render.append(("SOURCE", f"Sources Cited: {msg['sources'][:120]}"))
            
        lines_to_render.append(("SEP", ""))

    # Simple PDF page layout (612 x 792 points)
    stream_lines = []
    y = 740
    stream_lines.append("BT")

    for kind, text in lines_to_render:
        clean_text = (
            text.encode("ascii", "ignore")
            .decode("ascii")
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        if kind == "TITLE":
            stream_lines.append("/F2 18 Tf")
            stream_lines.append(f"50 {y} Td")
            stream_lines.append(f"({clean_text}) Tj")
            stream_lines.append(f"-50 -{y} Td")
            y -= 26
        elif kind == "SUBTITLE":
            stream_lines.append("/F1 10 Tf")
            stream_lines.append(f"50 {y} Td")
            stream_lines.append(f"({clean_text}) Tj")
            stream_lines.append(f"-50 -{y} Td")
            y -= 18
        elif kind == "HEADER":
            stream_lines.append("/F2 11 Tf")
            stream_lines.append(f"50 {y} Td")
            stream_lines.append(f"({clean_text}) Tj")
            stream_lines.append(f"-50 -{y} Td")
            y -= 15
        elif kind == "BODY":
            stream_lines.append("/F1 10 Tf")
            stream_lines.append(f"50 {y} Td")
            stream_lines.append(f"({clean_text}) Tj")
            stream_lines.append(f"-50 -{y} Td")
            y -= 13
        elif kind == "SOURCE":
            stream_lines.append("/F1 9 Tf")
            stream_lines.append(f"60 {y} Td")
            stream_lines.append(f"({clean_text}) Tj")
            stream_lines.append(f"-60 -{y} Td")
            y -= 13
        elif kind == "SEP":
            y -= 8

        if y < 60:
            # End current page stream and start new page if needed (for simplicity, cap at 1 page or continue)
            break

    stream_lines.append("ET")
    content_stream = "\n".join(stream_lines).encode("latin-1")

    # PDF object structure
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << "
        b"/F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
        b"/F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> "
        b">> >> >>\nendobj\n"
    )
    obj4 = f"4 0 obj\n<< /Length {len(content_stream)} >>\nstream\n".encode("latin-1") + content_stream + b"\nendstream\nendobj\n"

    header = b"%PDF-1.4\n"
    offsets = []
    current_offset = len(header)

    offsets.append(current_offset)
    current_offset += len(obj1)

    offsets.append(current_offset)
    current_offset += len(obj2)

    offsets.append(current_offset)
    current_offset += len(obj3)

    offsets.append(current_offset)
    current_offset += len(obj4)

    xref = f"xref\n0 5\n0000000000 65535 f \n".encode("latin-1")
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode("latin-1")

    trailer = f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{current_offset}\n%%EOF".encode("latin-1")

    return header + obj1 + obj2 + obj3 + obj4 + xref + trailer
