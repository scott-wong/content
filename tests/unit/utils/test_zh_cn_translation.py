from pathlib import Path

from utils import zh_cn_translation as zh


RULE_YAML = """documentation_complete: true

title: 'Example rule'

description: |-
    Install the example package.
    {{{ describe_package_install(package="example") }}}
    <pre>dnf install example</pre>

rationale: "The package provides an important security control."

severity: medium
"""

MULTILINE_QUOTED_YAML = """documentation_complete: true

title: 'Example rule'

description: '{{{ describe_file_owner(file="/etc/example", owner="root") }}}
{{{ describe_file_permissions(file="/etc/example", perms="0600") }}}'

rationale: |-
    Protect the example file.

severity: medium
"""


def test_inject_preserves_english_and_pre_block():
    original_description = zh.extract_field_value(RULE_YAML, "description")
    original_rationale = zh.extract_field_value(RULE_YAML, "rationale")
    chinese_description = (
        "<p>安装 example 软件包。</p>\n<pre>dnf install example</pre>"
    )

    translated = zh.inject_translation(RULE_YAML, "description", chinese_description)
    translated = zh.inject_translation(
        translated, "rationale", "<p>该软件包提供重要的安全控制。</p>"
    )

    english, chinese = zh._split_english(
        zh.extract_field_value(translated, "description"), "description"
    )
    assert english == original_description.rstrip("\n")
    assert chinese == chinese_description
    assert translated.count("<pre>dnf install example</pre>") == 2
    assert zh.extract_field_value(translated, "rationale").startswith(original_rationale)
    assert "rationale: |-" in translated


def test_multiline_single_quoted_field_is_converted_to_block_scalar():
    original = zh.extract_field_value(MULTILINE_QUOTED_YAML, "description")
    translated = zh.inject_translation(
        MULTILINE_QUOTED_YAML,
        "description",
        "<p><tt>/etc/example</tt> 必须由 <tt>root</tt> 所有，权限必须为 <tt>0600</tt>。</p>",
    )

    assert "description: |-\n" in translated
    english, chinese = zh._split_english(
        zh.extract_field_value(translated, "description"), "description"
    )
    assert english == original
    assert "中文说明" in translated
    assert "root" in chinese


def test_strip_target_fields_leaves_other_rule_content_unchanged(tmp_path):
    rule_path = tmp_path / "rule.yml"
    rule_path.write_text(RULE_YAML, encoding="utf-8")
    translated = zh.inject_translation(
        RULE_YAML, "description", "<p>安装 example 软件包。</p>"
    )
    translated = zh.inject_translation(
        translated, "rationale", "<p>该软件包提供重要的安全控制。</p>"
    )

    assert zh._strip_translated_fields(translated) == zh._strip_translated_fields(RULE_YAML)


def test_validate_rule_against_baseline(tmp_path):
    rule_dir = tmp_path / "linux_os" / "guide" / "services" / "example"
    rule_dir.mkdir(parents=True)
    rule_path = rule_dir / "rule.yml"
    translated = zh.inject_translation(
        RULE_YAML,
        "description",
        "<p>安装 example 软件包。</p>\n<pre>dnf install example</pre>",
    )
    translated = zh.inject_translation(
        translated, "rationale", "<p>该软件包提供重要的安全控制。</p>"
    )
    rule_path.write_text(translated, encoding="utf-8")

    baseline = tmp_path / "baseline.tsv"
    relative_path = str(rule_path.relative_to(tmp_path))
    baseline.write_text(
        "{}\t{}\t{}\n".format(
            relative_path,
            zh._field_hash(zh.extract_field_value(RULE_YAML, "description")),
            zh._field_hash(zh.extract_field_value(RULE_YAML, "rationale")),
        ),
        encoding="utf-8",
    )

    assert zh.validate_rules(
        paths=[relative_path],
        strict=True,
        root=str(tmp_path),
        baseline_path=str(baseline),
    ) == 0


def test_pre_trailing_whitespace_is_normalized_in_chinese_block():
    translated = zh.inject_translation(
        RULE_YAML,
        "description",
        "<p>安装 example 软件包。</p>\n<pre>dnf install example </pre>",
    )

    _, chinese = zh._split_english(
        zh.extract_field_value(translated, "description"), "description"
    )
    assert chinese == "<p>安装 example 软件包。</p>\n<pre>dnf install example</pre>"


def test_minus_pipe_block_is_converted_to_standard_block_scalar():
    source = """documentation_complete: true

description: -|
    English description.

rationale: -|
    English rationale.

severity: medium
"""
    translated = zh.inject_translation(
        source, "description", "<p>中文说明正文。</p>"
    )
    translated = zh.inject_translation(
        translated, "rationale", "<p>中文理由正文。</p>"
    )

    assert "description: |-\n    English description." in translated
    assert "rationale: |-\n    English rationale." in translated
    assert zh._field_hash(zh.extract_field_value(translated, "description").split(
        zh.MARKERS["description"])[0].rstrip("\n")
    ) == zh._field_hash("English description.")


def test_plain_chinese_text_is_wrapped_in_paragraph():
    translated = zh.inject_translation(
        RULE_YAML, "description", "安装 example 软件包。"
    )

    _, chinese = zh._split_english(
        zh.extract_field_value(translated, "description"), "description"
    )
    assert chinese.startswith("<p>安装 example 软件包。</p>")


def test_hash_ignores_trailing_whitespace():
    assert zh._field_hash("English text  \n") == zh._field_hash("English text")


def test_jinja_balance_checker():
    balanced = "{{% if product == 'rhel' %}}RHEL{{% else %}}Other{{% endif %}}"
    assert zh._jinja_balance_errors(balanced) == []
    assert zh._jinja_balance_errors("{{% if product == 'rhel' %}}RHEL")


def test_chinese_pre_blocks_may_be_omitted():
    translated = zh.inject_translation(
        RULE_YAML, "description", "<p>安装软件包并参考英文代码块。</p>"
    )
    _, chinese = zh._split_english(
        zh.extract_field_value(translated, "description"), "description"
    )
    assert zh.PRE_RE.findall(chinese) == []


def test_conditional_html_balance_checker():
    unbalanced = (
        "<p>text{{% if product == 'rhel' %}}</p><pre>x</pre>"
        "{{% else %}}<pre>y</pre>{{% endif %}}"
    )
    assert zh._html_balance_errors(unbalanced)
    balanced = (
        "<p>text</p>{{% if product == 'rhel' %}}<pre>x</pre>"
        "{{% else %}}<pre>y</pre>{{% endif %}}"
    )
    assert zh._html_balance_errors(balanced) == []
