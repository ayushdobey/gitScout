from fastapi import APIRouter

from app.api.v1.endpoints import analysis, auth, chat, evaluation, files, findings, graph, health, reports, repositories

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(repositories.router, prefix="/repositories", tags=["Repositories"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(files.router, tags=["Files & Explorer"])
api_router.include_router(graph.router, tags=["Dependency Graph"])
api_router.include_router(findings.router, tags=["Quality & Security"])
api_router.include_router(chat.router, tags=["Assistant & RAG"])
api_router.include_router(reports.router, tags=["Architecture Reports"])
api_router.include_router(evaluation.router, prefix="/evaluation", tags=["Evaluation & Benchmarks"])

