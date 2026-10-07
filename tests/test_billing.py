import billing


def test_usd_to_credits_and_majoration_pipeline():
    base = billing.usd_to_credits(2.5)
    final = billing.usd_to_final_credits(2.5)

    assert base == round(2.5 * billing.CREDIT_UNIT_PRICE_BY_DOLLAR, 2)
    assert final == round(base * billing.VIREEL_PRICE_MAJORATION, 2)


def test_estimate_llm_usage_cost_usd_for_known_and_unknown_provider():
    assert billing.estimate_llm_usage_cost_usd("unknown", 1000, 1000) == 0.0

    cost = billing.estimate_llm_usage_cost_usd("openai", 400000, 100000)
    assert cost == round((400000 / billing.OPEN_IA_INPUT_TOKEN_PER_DOLLAR) + (100000 / billing.OPEN_IA_OUTPUT_TOKEN_PER_DOLLAR), 6)


def test_calculate_credits_for_operation_enriches_payload():
    result = billing.calculate_credits_for_operation({"total_usd": 1.0, "foo": "bar"})

    assert result["foo"] == "bar"
    assert result["base_credits"] == billing.usd_to_credits(1.0)
    assert result["majoration_factor"] == billing.VIREEL_PRICE_MAJORATION
    assert result["final_credits"] == billing.apply_majoration(result["base_credits"])


def test_apply_majoration_rounds_and_multiplies():
    value = billing.apply_majoration(12.345)
    assert value == round(12.345 * billing.VIREEL_PRICE_MAJORATION, 2)


def test_estimate_reel_cost_usd_enables_optional_providers():
    result = billing.estimate_reel_cost_usd(
        duration_minutes=10,
        video_size_gb=1.0,
        uses_youtube_download=True,
        youtube_download_gb=0.5,
        uses_assembly=True,
        uses_openai=True,
        uses_gemini=True,
    )

    assert result["s3_usd"] > 0
    assert result["vps_usd"] > 0
    assert result["dataimpulse_usd"] > 0
    assert result["assembly_usd"] > 0
    assert result["total_usd"] >= result["s3_usd"] + result["vps_usd"]


def test_estimate_reel_cost_usd_disables_optional_costs():
    result = billing.estimate_reel_cost_usd(
        duration_minutes=5,
        video_size_gb=0.2,
        uses_youtube_download=False,
        youtube_download_gb=1.0,
        uses_assembly=False,
    )

    assert result["dataimpulse_usd"] == 0.0
    assert result["assembly_usd"] == 0.0


def test_estimate_caption_cost_usd_with_and_without_assembly():
    with_assembly = billing.estimate_caption_cost_usd(duration_minutes=5, uses_assembly=True)
    without_assembly = billing.estimate_caption_cost_usd(duration_minutes=5, uses_assembly=False)

    assert with_assembly["assembly_usd"] > 0
    assert without_assembly["assembly_usd"] == 0.0
    assert with_assembly["dataimpulse_usd"] == 0.0


def test_estimate_publication_cost_usd_scales_with_platform_count():
    one = billing.estimate_publication_cost_usd(platform_count=1, video_size_gb=0.5)
    three = billing.estimate_publication_cost_usd(platform_count=3, video_size_gb=0.5)
    assert three["total_usd"] > one["total_usd"]


def test_estimate_retention_storage_cost_usd_matches_spec_worked_example():
    # size_gb x retention_days x S3_STORAGE_COST_PER_GB_DAY, for the
    # spec's own worked example (4 GB, 30 days).
    cost = billing.estimate_retention_storage_cost_usd(4, 30)
    assert cost == round(4 * 30 * billing.S3_STORAGE_COST_PER_GB_DAY, 6)


def test_estimate_retention_storage_cost_usd_clamps_negative_inputs():
    assert billing.estimate_retention_storage_cost_usd(-1, 30) == 0.0
    assert billing.estimate_retention_storage_cost_usd(4, -1) == 0.0


def test_add_retention_cost_to_breakdown_is_additive_not_a_replacement():
    # Every existing key must survive unchanged -- retention is a NEW
    # component added on top, never a substitute for the existing S3
    # operation cost already in the breakdown.
    original = billing.estimate_reel_cost_usd(duration_minutes=10, video_size_gb=4.0)
    enriched = billing.add_retention_cost_to_breakdown(original, media_size_gb=4.0, retention_days=30)

    assert enriched["s3_usd"] == original["s3_usd"]
    assert enriched["vps_usd"] == original["vps_usd"]
    expected_retention_usd = billing.estimate_retention_storage_cost_usd(4.0, 30)
    assert enriched["retention_usd"] == expected_retention_usd
    assert enriched["total_usd"] == round(original["total_usd"] + expected_retention_usd, 6)


def test_add_retention_cost_to_breakdown_reuses_the_same_credit_converter():
    # The resulting final_credits must be exactly what
    # calculate_credits_for_operation itself would produce for the new
    # total_usd -- never a second, independently-computed conversion.
    base = {"total_usd": 0.15}
    enriched = billing.add_retention_cost_to_breakdown(base, media_size_gb=4.0, retention_days=30)

    expected = billing.calculate_credits_for_operation({
        "total_usd": round(0.15 + billing.estimate_retention_storage_cost_usd(4.0, 30), 6),
    })
    assert enriched["base_credits"] == expected["base_credits"]
    assert enriched["final_credits"] == expected["final_credits"]


def test_add_retention_cost_to_breakdown_zero_days_adds_nothing():
    base = {"total_usd": 0.5}
    enriched = billing.add_retention_cost_to_breakdown(base, media_size_gb=4.0, retention_days=0)
    assert enriched["retention_usd"] == 0.0
    assert enriched["total_usd"] == 0.5


