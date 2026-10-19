"""Multi-version generation: prompt instruction and output splitting."""

from app.services.llm import VARIANT_SEPARATOR, build_messages, split_variants


def test_single_variant_adds_no_instruction():
    assert VARIANT_SEPARATOR not in build_messages("src")[1]["content"]


def test_multiple_variants_ask_for_distinct_hooks():
    user = build_messages("src", variants=3)[1]["content"]
    assert "Write 3 distinct versions" in user
    assert "1) a short personal story" in user and "3) a numbered list" in user
    assert VARIANT_SEPARATOR in user


def test_split_variants_trims_and_drops_empty_parts():
    text = f"\nFirst post\n{VARIANT_SEPARATOR}\n Second post \n{VARIANT_SEPARATOR}\n\n"
    assert split_variants(text) == ["First post", "Second post"]
