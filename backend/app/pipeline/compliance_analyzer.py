"""
LLM-based compliance analysis with evidence-first approach.

Analyzes contract compliance using only retrieved evidence chunks,
never the full document. Returns structured JSON validated against
ComplianceResult schema.
"""

import json
from typing import List, Dict

from app.core.schemas import ComplianceResult, ComplianceState, Quote, EvidenceChunk
from app.pipeline.interfaces import IComplianceAnalyzer, AnalyzerError
from app.services.llm_client import LLMClient
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


# Compliance requirement definitions with rubrics
COMPLIANCE_REQUIREMENTS: Dict[str, Dict[str, str]] = {
    "password_management": {
        "question": "Password Management. The contract must require a documented password standard covering password length/strength, prohibition of default and known-compromised passwords, secure storage (no plaintext; salted hashing if stored), brute-force protections (lockout/rate limiting), prohibition on password sharing, vaulting of privileged credentials/recovery codes, and time-based rotation for break-glass credentials. Based on the contract language and exhibits, what is the compliance state for Password Management?",
        "rubric": """
Evaluate Password Management compliance per assignment requirements.

FULLY COMPLIANT if contract explicitly requires ALL of:
- Documented password standard (policy document)
- Password length/strength requirements (e.g., ≥12 chars, complexity)
- Prohibition of default/known-compromised passwords
- Secure storage (no plaintext; salted hashing if stored)
- Brute-force protections (lockout/rate limiting)
- Prohibition on password sharing
- Vaulting of privileged credentials/recovery codes (e.g., break-glass accounts)
- Time-based rotation for break-glass credentials

PARTIALLY COMPLIANT if contract addresses some but not all requirements (e.g., mentions passwords but lacks vaulting or brute-force protection).

NON-COMPLIANT if no password management requirements found in evidence.
"""
    },
    "it_asset_management": {
        "question": "IT Asset Management. The contract must require an in-scope asset inventory (including cloud accounts/subscriptions, workloads, databases, security tooling), define minimum inventory fields, require at least quarterly reconciliation/review, and require secure configuration baselines with drift remediation and prohibition of insecure defaults. Based on the contract language and exhibits, what is the compliance state for IT Asset Management?",
        "rubric": """
Evaluate IT Asset Management compliance per assignment requirements.

FULLY COMPLIANT if contract explicitly requires ALL of:
- In-scope asset inventory (cloud accounts/subscriptions, workloads, databases, security tooling)
- Defined minimum inventory fields (what data must be tracked per asset)
- At least quarterly reconciliation/review of asset inventory
- Secure configuration baselines (hardening standards)
- Drift remediation (detect and fix configuration drift)
- Prohibition of insecure defaults

PARTIALLY COMPLIANT if contract addresses some but not all requirements (e.g., mentions inventory but no quarterly review or drift remediation).

NON-COMPLIANT if no IT asset management requirements found in evidence.
"""
    },
    "security_training": {
        "question": "Security Training & Background Checks. The contract must require security awareness training on hire and at least annually, and background screening for personnel with access to Company Data to the extent permitted by law, including maintaining a screening policy and attestation/evidence. Based on the contract language and exhibits, what is the compliance state for Security Training and Background Checks?",
        "rubric": """
Evaluate Security Training & Background Checks compliance per assignment requirements.

FULLY COMPLIANT if contract explicitly requires ALL of:
- Security awareness training on hire (initial onboarding training)
- Security awareness training at least annually (ongoing/refresher training)
- Background screening for personnel with access to Company Data
- Background screening to the extent permitted by law (legal compliance clause)
- Screening policy maintained by vendor
- Attestation/evidence of training and screening (documentation requirements)

PARTIALLY COMPLIANT if contract addresses some but not all requirements (e.g., mentions training but no frequency, or screening but no policy/attestation).

NON-COMPLIANT if no security training or background check requirements found in evidence.
"""
    },
    "tls_encryption": {
        "question": "Data in Transit Encryption. The contract must require encryption of Company Data in transit using TLS 1.2+ (preferably TLS 1.3 where feasible) for Company-to-Service traffic, administrative access pathways, and applicable Service-to-Subprocessor transfers, with certificate management and avoidance of insecure cipher suites. Based on the contract language and exhibits, what is the compliance state for Data in Transit Encryption?",
        "rubric": """
Evaluate Data in Transit Encryption compliance per assignment requirements.

FULLY COMPLIANT if contract explicitly requires ALL of:
- Encryption of Company Data in transit
- TLS 1.2 or higher (TLS 1.2+ minimum, TLS 1.3 preferred where feasible)
- Coverage for Company-to-Service traffic (client to vendor)
- Coverage for administrative access pathways (admin consoles, management interfaces)
- Coverage for Service-to-Subprocessor transfers (if applicable/disclosed)
- Certificate management (renewal, expiration, revocation procedures)
- Avoidance of insecure cipher suites (prohibited weak ciphers)

PARTIALLY COMPLIANT if contract addresses some but not all requirements (e.g., mentions TLS but no version, or lacks certificate management).

NON-COMPLIANT if no data in transit encryption requirements found in evidence.
"""
    },
    "authn_authz": {
        "question": "Network Authentication & Authorization Protocols. The contract must specify the authentication mechanisms (e.g., SAML SSO for users, OAuth/token-based for APIs), require MFA for privileged/production access, require secure admin pathways (bastion/secure gateway) with session logging, and require RBAC authorization. Based on the contract language and exhibits, what is the compliance state for Network Authentication and Authorization Protocols?",
        "rubric": """
Evaluate Network Authentication & Authorization compliance per assignment requirements.

FULLY COMPLIANT if contract explicitly requires ALL of:
- Specified authentication mechanisms (e.g., SAML SSO for users, OAuth/token-based for APIs)
- MFA (multi-factor authentication) for privileged/production access
- Secure admin pathways (bastion host, secure gateway, jump server)
- Session logging (audit trail of access sessions)
- RBAC (role-based access control) authorization

PARTIALLY COMPLIANT if contract addresses some but not all requirements (e.g., mentions MFA but no RBAC, or no session logging).

NON-COMPLIANT if no authentication or authorization requirements found in evidence.
"""
    }
}


class ComplianceAnalyzer(IComplianceAnalyzer):
    """
    Analyzes compliance requirements using LLM and retrieved evidence.
    
    Evidence-first: LLM receives only top-k evidence chunks, never full document.
    Schema-validated: Outputs must match ComplianceResult Pydantic schema.
    """
    
    def __init__(self, llm_client: LLMClient):
        """
        Initialize compliance analyzer.
        
        Args:
            llm_client: LLM client for generation
        """
        self.llm_client = llm_client
    
    async def analyze(
        self,
        question: str,
        evidence_chunks: List[EvidenceChunk]
    ) -> ComplianceResult:
        """
        Analyze compliance for a single requirement using evidence.
        
        Args:
            question: Compliance question (requirement ID key)
            evidence_chunks: Retrieved evidence chunks (top-k)
            
        Returns:
            ComplianceResult with analysis
            
        Raises:
            AnalyzerError: If analysis fails critically
        """
        try:
            # Get requirement definition
            if question not in COMPLIANCE_REQUIREMENTS:
                raise AnalyzerError(f"Unknown requirement: {question}")
            
            requirement = COMPLIANCE_REQUIREMENTS[question]
            
            # Build prompt with evidence
            prompt = self._build_prompt(requirement, evidence_chunks)
            
            # Generate response
            logger.info(f"Analyzing requirement: {requirement['question'][:50]}...")
            response = await self.llm_client.generate(
                prompt=prompt,
                temperature=0.3,  # Low temperature for consistent output
                max_tokens=800
            )
            
            # Parse JSON response
            result = self._parse_response(response, requirement)
            
            if result:
                logger.info(
                    f"Analysis complete: {result.compliance_state.value}, "
                    f"confidence={result.confidence}"
                )
                return result
            
            # Parsing failed - retry with fix prompt
            logger.warning("Initial JSON parse failed, retrying with fix prompt")
            result = await self._retry_with_fix_prompt(response, requirement)
            
            if result:
                return result
            
            # Both attempts failed - return fallback
            logger.error("JSON parsing failed after retry, returning fallback result")
            return self._create_fallback_result(requirement)
            
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}", exc_info=True)
            raise AnalyzerError(f"Compliance analysis failed: {str(e)}")
    
    def _build_prompt(
        self,
        requirement: Dict[str, str],
        evidence_chunks: List[EvidenceChunk]
    ) -> str:
        """
        Build LLM prompt with evidence and rubric.
        
        Args:
            requirement: Requirement definition with question and rubric
            evidence_chunks: Evidence chunks to analyze
            
        Returns:
            Formatted prompt string
        """
        # Format evidence with page references
        evidence_text = self._format_evidence(evidence_chunks)
        
        prompt = f"""You are a contract compliance analyst. Analyze the following contract evidence and determine compliance.

REQUIREMENT:
{requirement['question']}

RUBRIC:
{requirement['rubric']}

EVIDENCE (from contract):
{evidence_text}

TASK:
Based ONLY on the evidence provided above, determine the compliance state and provide your analysis.

OUTPUT FORMAT (JSON only, no other text):
{{
  "compliance_state": "Fully Compliant" | "Partially Compliant" | "Non-Compliant",
  "confidence": <integer 0-100>,
  "relevant_quotes": [
    {{"text": "exact quote from evidence", "page_start": <page_num>, "page_end": <page_num>}}
  ],
  "rationale": "Brief explanation of determination based on evidence"
}}

IMPORTANT:
- compliance_state must be EXACTLY one of: "Fully Compliant", "Partially Compliant", "Non-Compliant"
- Include only verbatim quotes from the evidence above
- Reference page numbers from evidence labels
- Return ONLY valid JSON, no additional text

JSON:"""
        
        return prompt
    
    def _format_evidence(self, evidence_chunks: List[EvidenceChunk]) -> str:
        """
        Format evidence chunks with page labels.
        
        Args:
            evidence_chunks: Evidence chunks to format
            
        Returns:
            Formatted evidence text
        """
        if not evidence_chunks:
            return "[No relevant evidence found in contract]"
        
        formatted = []
        for i, chunk in enumerate(evidence_chunks, 1):
            page_ref = f"[Pages {chunk.page_start}"
            if chunk.page_end != chunk.page_start:
                page_ref += f"-{chunk.page_end}"
            page_ref += "]"
            
            formatted.append(f"Evidence {i} {page_ref}:\n{chunk.text}")
        
        return "\n\n".join(formatted)
    
    def _parse_response(
        self,
        response: str,
        requirement: Dict[str, str]
    ) -> ComplianceResult:
        """
        Parse LLM response into ComplianceResult.
        
        Args:
            response: LLM generated text
            requirement: Requirement definition
            
        Returns:
            ComplianceResult if parsing succeeds, None otherwise
        """
        try:
            # Extract JSON from response (LLM might add text before/after)
            json_str = self._extract_json(response)
            data = json.loads(json_str)
            
            # Parse compliance_state enum
            state_str = data["compliance_state"]
            if state_str == "Fully Compliant":
                state = ComplianceState.FULLY_COMPLIANT
            elif state_str == "Partially Compliant":
                state = ComplianceState.PARTIALLY_COMPLIANT
            elif state_str == "Non-Compliant":
                state = ComplianceState.NON_COMPLIANT
            else:
                logger.warning(f"Invalid compliance state: {state_str}")
                return None
            
            # Parse quotes
            quotes = []
            for q in data.get("relevant_quotes", []):
                quote = Quote(
                    text=q["text"],
                    page_start=q["page_start"],
                    page_end=q["page_end"],
                    validated=False  # Will be validated by QuoteValidator
                )
                quotes.append(quote)
            
            # Build ComplianceResult
            result = ComplianceResult(
                compliance_question=requirement["question"],
                compliance_state=state,
                confidence=int(data["confidence"]),
                relevant_quotes=quotes,
                rationale=data["rationale"]
            )
            
            return result
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"JSON parse error: {str(e)}")
            return None
    
    def _extract_json(self, response: str) -> str:
        """
        Extract JSON object from response text.
        
        Args:
            response: Raw response text
            
        Returns:
            Extracted JSON string
        """
        # Find first { and last }
        start = response.find('{')
        end = response.rfind('}')
        
        if start != -1 and end != -1 and end > start:
            return response[start:end+1]
        
        return response
    
    async def _retry_with_fix_prompt(
        self,
        invalid_response: str,
        requirement: Dict[str, str]
    ) -> ComplianceResult:
        """
        Retry parsing with a fix prompt.
        
        Args:
            invalid_response: Previous invalid response
            requirement: Requirement definition
            
        Returns:
            ComplianceResult if successful, None otherwise
        """
        # Truncate invalid response to avoid huge logs
        truncated = invalid_response[:500] if len(invalid_response) > 500 else invalid_response
        
        fix_prompt = f"""The previous response was not valid JSON. Please fix it.

REQUIRED FORMAT:
{{
  "compliance_state": "Fully Compliant" | "Partially Compliant" | "Non-Compliant",
  "confidence": <integer 0-100>,
  "relevant_quotes": [
    {{"text": "quote", "page_start": <page>, "page_end": <page>}}
  ],
  "rationale": "explanation"
}}

PREVIOUS OUTPUT (invalid):
{truncated}

Return ONLY valid JSON with the correct format:"""
        
        try:
            response = await self.llm_client.generate(
                prompt=fix_prompt,
                temperature=0.1,
                max_tokens=600
            )
            
            return self._parse_response(response, requirement)
            
        except Exception as e:
            logger.warning(f"Retry failed: {str(e)}")
            return None
    
    def _create_fallback_result(
        self,
        requirement: Dict[str, str]
    ) -> ComplianceResult:
        """
        Create fallback result when parsing fails.
        
        Args:
            requirement: Requirement definition
            
        Returns:
            Fallback ComplianceResult
        """
        return ComplianceResult(
            compliance_question=requirement["question"],
            compliance_state=ComplianceState.NON_COMPLIANT,
            confidence=10,
            relevant_quotes=[],
            rationale="Model output could not be parsed."
        )


def get_requirement_ids() -> List[str]:
    """
    Get list of all compliance requirement IDs.
    
    Returns:
        List of requirement ID strings
    """
    return list(COMPLIANCE_REQUIREMENTS.keys())
