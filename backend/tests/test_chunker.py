from app.services.chunker import SyntaxAwareChunker

SAMPLE_CODE = """# Module Header
import os
import sys

GLOBAL_TIMEOUT = 30

@app.route("/items")
def list_items(limit: int = 100) -> list:
    \"\"\"Return paginated items.\"\"\"
    items = []
    for i in range(limit):
        items.append({"id": i})
    return items

class ItemManager:
    \"\"\"Manages lifecycle of items.\"\"\"
    def __init__(self, db_conn):
        self.db = db_conn

    def delete_item(self, item_id: int) -> bool:
        return True
"""


def test_syntax_aware_chunking():
    """Verify that chunks split cleanly at function and class AST boundaries."""
    chunker = SyntaxAwareChunker()
    chunks = chunker.chunk_python_source(SAMPLE_CODE, "app/api.py")

    assert len(chunks) >= 2

    # Check function chunk
    func_chunk = next(c for c in chunks if c.symbol_name == "list_items")
    assert func_chunk.start_line <= 7  # includes @app.route
    assert "def list_items" in func_chunk.content
    assert "return items" in func_chunk.content

    # Check class chunk
    class_chunk = next(c for c in chunks if c.symbol_name == "ItemManager")
    assert "class ItemManager:" in class_chunk.content
    assert "delete_item" in class_chunk.content


def test_generic_text_chunking():
    """Verify line-window chunking on markdown/configuration files."""
    chunker = SyntaxAwareChunker(max_chunk_lines=20)
    markdown_content = "\n".join([f"# Section {i}\nParagraph content line {i}." for i in range(50)])
    chunks = chunker.chunk_text_source(markdown_content, "docs/guide.md")

    assert len(chunks) > 1
    for c in chunks:
        assert c.start_line <= c.end_line
        assert c.token_count > 0

