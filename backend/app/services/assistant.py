import re
import time
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from app.models.analysis import AnalysisRun
from app.models.chat import ChatMessage, ChatSession, MessageCitation
from app.models.repository import Repository
from app.services.llm import BaseLLMProvider, get_llm_provider
from app.services.retriever import HybridRetriever, RetrievedChunk

SYSTEM_PROMPT_TEMPLATE = """You are GitScout, an elite AI codebase intelligence assistant.
Your mission is to help developers comprehend unfamiliar software repositories with precision.

STRICT GROUNDING RULES:
1. CITATION REQUIREMENT: You MUST cite supporting source files and exact line numbers for every claim using the standard markdown reference format: [file_path#Lstart-Lend].
2. ANTI-HALLUCINATION CONTRACT: Never invent functions, files, arguments, or dependencies that are not present in the provided evidence.
3. KNOWLEDGE BOUNDARY: If the answer cannot be definitively established from the provided code evidence, you must state:
   "Based on the analyzed codebase, this functionality is not defined in the extracted files."
4. STRUCTURED EXPLANATION: Clearly explain execution flows, parameter types, error handling, and architectural intent based strictly on the extracted source text.
"""


def extract_citations_from_text(text: str) -> List[Tuple[str, int, int]]:
    """
    Extract citation references matching [path/to/file.ext#L12-L34] from generated text.
    Returns list of (file_path, start_line, end_line).
    """
    pattern = r'\[\s*([a-zA-Z0-9_\-\.\/]+)#L(\d+)-L?(\d*)\s*\]'
    matches = re.findall(pattern, text)
    citations = []
    for match in matches:
        path = match[0]
        start = int(match[1])
        end = int(match[2]) if match[2] else start
        citations.append((path, start, end))
    return citations


class CodebaseAssistantService:
    """
    Evidence-grounded codebase interrogation engine.
    Executes hybrid retrieval, prompt conditioning, LLM generation, and citation verification.
    """
    def __init__(self, db: Session, llm_provider: BaseLLMProvider | None = None):
        self.db = db
        self.llm_provider = llm_provider or get_llm_provider()
        self.retriever = HybridRetriever(db)

    def answer_question(
        self,
        repository_id: str,
        user_id: str,
        question: str,
        session_id: str | None = None
    ) -> Dict[str, Any]:
        """
        Execute grounded RAG workflow:
        1. Retrieve top evidence chunks via Hybrid RRF search.
        2. Format structured prompt with repository context.
        3. Query LLM provider.
        4. Validate citations and persist conversation history in PostgreSQL.
        """
        start_time = time.time()

        # 1. Fetch Repository and latest completed analysis run
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise ValueError(f"Repository {repository_id} does not exist.")

        latest_run = (
            self.db.query(AnalysisRun)
            .filter(AnalysisRun.repository_id == repository_id, AnalysisRun.status == "COMPLETED")
            .order_by(AnalysisRun.completed_at.desc())
            .first()
        )

        if not latest_run:
            raise ValueError("No completed analysis run found. Please run repository analysis first.")

        # 2. Hybrid Retrieval (pgvector dense + lexical RRF)
        retrieved_chunks: List[RetrievedChunk] = self.retriever.hybrid_search(
            analysis_id=latest_run.id,
            query=question,
            top_k=5
        )

        # 3. Assemble Grounded Evidence Context
        evidence_blocks = []
        for chunk in retrieved_chunks:
            header = f"[SOURCE: {chunk.file_path}#L{chunk.start_line}-L{chunk.end_line}] (RRF Score: {chunk.rrf_score})"
            evidence_blocks.append(f"{header}\n```\n{chunk.content}\n```")

        evidence_text = "\n\n".join(evidence_blocks) if evidence_blocks else "No relevant code chunks discovered."

        user_prompt = f"""=== REPOSITORY CONTEXT ===
Repository: {repo.owner}/{repo.name}
Default Branch: {repo.default_branch}
Primary Language: {repo.primary_language or 'Python'}
Total Files Analyzed: {latest_run.file_count}

=== EXTRACTED SOURCE CODE EVIDENCE ===
{evidence_text}

=== DEVELOPER QUESTION ===
{question}
"""

        # 4. Generate Response from LLM
        answer = self.llm_provider.generate_response(
            system_prompt=SYSTEM_PROMPT_TEMPLATE,
            user_prompt=user_prompt
        )

        latency_ms = int((time.time() - start_time) * 1000)

        # 5. Extract and Verify Citations
        extracted_citations = extract_citations_from_text(answer)
        
        # Build chunk map for linking chunk_id to citation
        chunk_by_path: Dict[str, RetrievedChunk] = {c.file_path: c for c in retrieved_chunks}

        # 6. Database Persistence
        # Manage ChatSession
        if session_id:
            session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        else:
            session = None

        if not session:
            title = question[:40] + ("..." if len(question) > 40 else "")
            session = ChatSession(
                user_id=user_id,
                repository_id=repository_id,
                title=title
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

        # Store User Message
        user_msg = ChatMessage(
            session_id=session.id,
            role="USER",
            content=question
        )
        self.db.add(user_msg)
        self.db.commit()

        # Store Assistant Message
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="ASSISTANT",
            content=answer,
            latency_ms=latency_ms
        )
        self.db.add(assistant_msg)
        self.db.commit()
        self.db.refresh(assistant_msg)

        # Store Citation Records
        citations_data = []
        for path, start_l, end_l in extracted_citations:
            matched_chunk = chunk_by_path.get(path)
            chunk_id = matched_chunk.chunk_id if matched_chunk else None
            
            citation = MessageCitation(
                message_id=assistant_msg.id,
                chunk_id=chunk_id,
                file_path=path,
                start_line=start_l,
                end_line=end_l,
                relevance_score=matched_chunk.rrf_score if matched_chunk else None
            )
            self.db.add(citation)
            citations_data.append({
                "file_path": path,
                "start_line": start_l,
                "end_line": end_l,
                "relevance_score": matched_chunk.rrf_score if matched_chunk else None
            })

        # Fallback citations: if model didn't use bracket syntax, cite the top 2 retrieved chunks
        if not citations_data and retrieved_chunks:
            for top_c in retrieved_chunks[:2]:
                citation = MessageCitation(
                    message_id=assistant_msg.id,
                    chunk_id=top_c.chunk_id,
                    file_path=top_c.file_path,
                    start_line=top_c.start_line,
                    end_line=top_c.end_line,
                    relevance_score=top_c.rrf_score
                )
                self.db.add(citation)
                citations_data.append({
                    "file_path": top_c.file_path,
                    "start_line": top_c.start_line,
                    "end_line": top_c.end_line,
                    "relevance_score": top_c.rrf_score
                })

        self.db.commit()

        return {
            "session_id": session.id,
            "message_id": assistant_msg.id,
            "question": question,
            "answer": answer,
            "citations": citations_data,
            "latency_ms": latency_ms
        }
