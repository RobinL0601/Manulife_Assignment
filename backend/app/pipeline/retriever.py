"""
BM25-based evidence retrieval for compliance requirements.

Retrieves top-k most relevant document chunks for each compliance requirement
using BM25 scoring over normalized text.
"""

from typing import List, Dict
from rank_bm25 import BM25Okapi

from app.core.schemas import Chunk, EvidenceChunk
from app.pipeline.interfaces import IRetriever, RetrieverError
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


# Curated keyword queries for each compliance requirement
REQUIREMENT_QUERIES: Dict[str, List[str]] = {
    "password_management": [
        "password", "passwords", "credential", "credentials",
        "authentication", "authenticate", "passphrase",
        "complexity", "length", "characters", "uppercase", "lowercase",
        "special character", "numeric", "alphanumeric",
        "rotation", "expire", "expiration", "change", "reset",
        "salted hash", "hashing", "bcrypt", "pbkdf2",
        "lockout", "rate limiting", "brute force", "attempts",
        "multi-factor", "MFA", "2FA", "two-factor",
        "break-glass", "emergency access", "vault", "secret management"
    ],
    
    "it_asset_management": [
        "asset", "assets", "inventory", "inventories",
        "hardware", "software", "device", "devices",
        "tracking", "monitor", "monitoring", "management",
        "CMDB", "configuration management", "discovery",
        "lifecycle", "provisioning", "decommission",
        "quarterly reconciliation", "reconcile", "audit trail",
        "drift remediation", "compliance scan", "baseline",
        "patch management", "vulnerability", "update"
    ],
    
    "security_training": [
        "training", "awareness", "education", "course",
        "security awareness", "cybersecurity training",
        "phishing", "social engineering", "incident response",
        "background check", "background screening", "screening",
        "criminal history", "employment verification",
        "security clearance", "vetting", "personnel security",
        "onboarding", "annual training", "refresher",
        "attestation", "acknowledgment", "certification",
        "evidence", "completion record", "certificate"
    ],
    
    "tls_encryption": [
        "TLS", "SSL", "transport layer security",
        "encryption", "encrypted", "encrypt",
        "in transit", "data in transit", "transmission",
        "TLS 1.2", "TLS 1.3", "protocol version",
        "cipher suite", "cipher", "encryption algorithm",
        "certificate", "cert", "CA", "certificate authority",
        "cert management", "certificate lifecycle", "renewal",
        "PKI", "public key infrastructure",
        "HTTPS", "secure channel", "encrypted channel"
    ],
    
    "authn_authz": [
        "authentication", "authorization", "access control",
        "identity", "IAM", "identity management",
        "SSO", "single sign-on", "federated",
        "SAML", "OAuth", "OpenID", "OIDC",
        "RBAC", "role-based", "access control",
        "least privilege", "privilege", "permissions",
        "session", "session management", "timeout",
        "session logging", "audit log", "access log",
        "bastion", "jump host", "privileged access",
        "MFA", "multi-factor", "two-factor"
    ]
}


class BM25Retriever(IRetriever):
    """
    BM25-based retriever for finding relevant evidence chunks.
    
    Uses BM25Okapi algorithm to score chunks against requirement queries.
    Returns chunks as EvidenceChunk objects with relevance scores.
    """
    
    def __init__(self):
        """Initialize BM25 retriever."""
        self._corpus_chunks = None
        self._bm25 = None
    
    def retrieve(
        self,
        query: str,
        chunks: List[Chunk],
        top_k: int = 5
    ) -> List[EvidenceChunk]:
        """
        Retrieve top-k most relevant chunks using BM25 scoring.
        
        Args:
            query: Requirement ID (key from REQUIREMENT_QUERIES)
            chunks: List of document chunks to search
            top_k: Number of chunks to retrieve
            
        Returns:
            List of EvidenceChunk objects sorted by relevance score (descending)
            
        Raises:
            RetrieverError: If retrieval fails
        """
        try:
            if not chunks:
                logger.warning("No chunks provided for retrieval")
                return []
            
            # Get query keywords for this requirement
            if query not in REQUIREMENT_QUERIES:
                logger.warning(f"Unknown requirement ID: {query}, using query as-is")
                query_keywords = query.lower().split()
            else:
                query_keywords = REQUIREMENT_QUERIES[query]
            
            # Tokenize corpus (use normalized text for matching)
            tokenized_corpus = [
                chunk.normalized_text.split() for chunk in chunks
            ]
            
            # Build BM25 index
            bm25 = BM25Okapi(tokenized_corpus)
            
            # Score all chunks
            scores = bm25.get_scores(query_keywords)
            
            # Create (chunk, score) pairs
            chunk_scores = list(zip(chunks, scores))
            
            # Sort by score descending
            chunk_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Take top-k
            top_chunks = chunk_scores[:top_k]
            
            # Normalize scores to 0-1 range (BM25 scores can be > 1)
            if top_chunks:
                max_score = max(score for _, score in top_chunks)
                if max_score > 0:
                    # Normalize: score / max_score (top score becomes 1.0)
                    normalized_scores = [score / max_score for _, score in top_chunks]
                else:
                    # All scores are 0 - assign 0.0
                    normalized_scores = [0.0] * len(top_chunks)
            else:
                normalized_scores = []
            
            # Convert to EvidenceChunk objects
            evidence_chunks = []
            for (chunk, _), normalized_score in zip(top_chunks, normalized_scores):
                evidence_chunk = EvidenceChunk(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,  # Original text, not mutated
                    normalized_text=chunk.normalized_text,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    char_range=chunk.char_range,
                    relevance_score=float(normalized_score)  # Now 0-1 range
                )
                evidence_chunks.append(evidence_chunk)
            
            logger.info(
                f"Retrieved {len(evidence_chunks)} chunks for requirement '{query}' "
                f"(top score: {evidence_chunks[0].relevance_score:.2f})" if evidence_chunks else
                f"No chunks retrieved for requirement '{query}'"
            )
            
            return evidence_chunks
            
        except Exception as e:
            logger.error(f"Retrieval failed: {str(e)}", exc_info=True)
            raise RetrieverError(f"Failed to retrieve evidence: {str(e)}")


def get_requirement_ids() -> List[str]:
    """
    Get list of all requirement IDs.
    
    Returns:
        List of requirement ID strings
    """
    return list(REQUIREMENT_QUERIES.keys())


def get_requirement_query(requirement_id: str) -> List[str]:
    """
    Get query keywords for a specific requirement.
    
    Args:
        requirement_id: Requirement ID
        
    Returns:
        List of query keywords
        
    Raises:
        KeyError: If requirement_id not found
    """
    return REQUIREMENT_QUERIES[requirement_id]
