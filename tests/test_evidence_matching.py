from nerve_center.discovery.models import JobProvenance, NormalizedJobOpening
from nerve_center.profile.models import (
    CareerClaim,
    ClaimCategory,
    EvidenceOrigin,
    EvidenceReference,
)
from nerve_center.scoring.evidence import CareerEvidenceMatcher
from nerve_center.scoring.models import DomainRelationship, EvidenceRelationship


def claim(
    claim_id: str,
    category: ClaimCategory,
    label: str,
    statement: str,
) -> CareerClaim:
    return CareerClaim(
        id=claim_id,
        category=category,
        label=label,
        statement=statement,
        confidence=1,
        evidence=[
            EvidenceReference(
                origin=EvidenceOrigin.USER_CONFIRMED,
                locator=f"profile:{claim_id}",
                excerpt=statement,
            )
        ],
    )


def opening(description: str) -> NormalizedJobOpening:
    return NormalizedJobOpening(
        id="job-1",
        company_id="company-1",
        company_name="Example",
        company_domain="example.com",
        title="Product Leader",
        description=description,
        source_url="https://example.com/job",
        canonical_url="https://example.com/job",
        provenance=[
            JobProvenance(
                source_id="source-1",
                connector="test",
                parser_version="v1",
                source_url="https://example.com/job",
            )
        ],
    )


def test_matcher_connects_semantically_equivalent_product_work_with_provenance() -> None:
    matcher = CareerEvidenceMatcher()
    career_claim = claim(
        "claim-strategy",
        ClaimCategory.CAPABILITY,
        "Portfolio strategy",
        "Owned portfolio strategy and investment sequencing across product lines.",
    )

    matches = matcher.match_requirement(
        "Set product vision and prioritize roadmap investments.",
        [career_claim],
    )

    assert matches[0].claim_id == career_claim.id
    assert matches[0].relationship is EvidenceRelationship.EQUIVALENT
    assert matches[0].shared_concepts == ["prioritization", "product_strategy"]
    assert matches[0].evidence_locators == ["profile:claim-strategy"]


def test_matcher_marks_generic_cross_domain_support_as_transferable() -> None:
    matcher = CareerEvidenceMatcher()
    leadership = claim(
        "claim-leadership",
        ClaimCategory.LEADERSHIP_SCOPE,
        "Matrix leadership",
        "Aligned matrixed teams and stakeholders to deliver major programs.",
    )

    matches = matcher.match_requirement(
        "Align cross functional teams to execute a launch.",
        [leadership],
    )

    assert matches[0].relationship is EvidenceRelationship.TRANSFERABLE


def test_matcher_does_not_infer_unsupported_credentials() -> None:
    matcher = CareerEvidenceMatcher()
    leadership = claim(
        "claim-leadership",
        ClaimCategory.LEADERSHIP_SCOPE,
        "Security leadership",
        "Led teams building security software.",
    )

    assert matcher.match_requirement("Active security clearance required.", [leadership]) == []


def test_matcher_does_not_treat_every_use_of_platform_as_product_evidence() -> None:
    matcher = CareerEvidenceMatcher()
    product_platform = claim(
        "claim-platform",
        ClaimCategory.CAPABILITY,
        "Platform product strategy",
        "Owned product platform strategy and roadmap decisions.",
    )

    assert matcher.match_requirement(
        "Strong fluency with modern cloud platforms, Kubernetes, and distributed systems.",
        [product_platform],
    ) == []


def test_domain_assessment_distinguishes_direct_adjacent_transferable_and_mismatch() -> None:
    matcher = CareerEvidenceMatcher()
    finance = claim(
        "claim-finance",
        ClaimCategory.INDUSTRY,
        "Financial services",
        "Built products for banking and payments customers.",
    )
    property_claim = claim(
        "claim-property",
        ClaimCategory.INDUSTRY,
        "Property technology",
        "Built products for real estate and property management.",
    )
    generic_match = matcher.match_requirement(
        "Lead product strategy and roadmap prioritization.",
        [
            claim(
                "claim-product",
                ClaimCategory.CAPABILITY,
                "Product strategy",
                "Owned product strategy and portfolio prioritization.",
            )
        ],
    )

    direct = matcher.assess_domain(opening("Payments platform for banks."), [finance], [])
    adjacent = matcher.assess_domain(
        opening("Software for lawn care providers."), [property_claim], []
    )
    transferable = matcher.assess_domain(
        opening("Clinical workflow product for hospitals."),
        [property_claim],
        generic_match,
    )
    mismatch = matcher.assess_domain(
        opening("Clinical workflow product for hospitals."),
        [property_claim],
        [],
    )

    assert direct.relationship is DomainRelationship.DIRECT
    assert direct.matched_claim_ids == ["claim-finance"]
    assert adjacent.relationship is DomainRelationship.ADJACENT
    assert transferable.relationship is DomainRelationship.TRANSFERABLE
    assert mismatch.relationship is DomainRelationship.MISMATCH
