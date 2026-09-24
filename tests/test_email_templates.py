import pytest

import email_templates


def test_every_template_renders_with_a_representative_context():
    # A smoke test that every template's html/subject placeholders are
    # satisfied by a plausible real-world context -- catches a typo'd
    # placeholder (e.g. "{amout}") immediately instead of at send time.
    contexts = {
        "credit_purchase": {"amount": 9.99, "credits": 100},
        "subscription_purchase": {"amount": 29.99, "plan_name": "Pro"},
        "subscription_renewal": {"amount": 29.99, "plan_name": "Pro"},
        "payment_failed": {
            "amount": 29.99, "plan_name": "Pro",
            "retry_message": "Une nouvelle tentative aura lieu le 01/01/2027.",
            "update_payment_url": "https://billing.stripe.com/session/abc",
        },
    }
    assert set(contexts.keys()) == set(email_templates.EMAIL_TEMPLATES.keys())

    for template_key, context in contexts.items():
        rendered = email_templates.render_email(template_key, **context)
        assert "{" not in rendered.subject
        assert "}" not in rendered.subject
        assert "{" not in rendered.html
        assert "}" not in rendered.html


def test_render_email_unknown_template_raises_key_error():
    with pytest.raises(KeyError):
        email_templates.render_email("not_a_real_template", amount=1)


def test_render_email_missing_context_raises():
    with pytest.raises(KeyError):
        email_templates.render_email("credit_purchase", amount=9.99)  # missing "credits"


def test_credit_purchase_template_includes_amount_and_credits():
    rendered = email_templates.render_email("credit_purchase", amount=9.99, credits=100)
    assert "9.99" in rendered.html
    assert "100" in rendered.html


def test_payment_failed_template_includes_update_payment_link():
    rendered = email_templates.render_email(
        "payment_failed", amount=29.99, plan_name="Pro",
        retry_message="Nouvelle tentative le 01/01/2027.",
        update_payment_url="https://billing.stripe.com/session/abc",
    )
    assert "https://billing.stripe.com/session/abc" in rendered.html
    assert "Pro" in rendered.subject
