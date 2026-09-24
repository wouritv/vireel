"""
email_templates.py -- Single editable source of truth for every transactional
email this backend sends via Brevo (credit purchase, subscription purchase,
subscription renewal, failed monthly payment). Edit the subject/html strings
below directly; no other file needs to change to update copy or styling.

Account creation and password reset are NOT here: those are sent by
Supabase Auth itself (the frontend calls supabase.auth.signUp()/
resetPasswordForEmail() directly), so their content lives in the Supabase
dashboard instead (Authentication -> Email Templates), not in this repo.

Each template's html is a plain Python format string -- render_email()
fills in "{placeholder}" fields from the context passed to it. Keep every
placeholder used in a template's html declared as a required key in that
template's `fields` tuple below (send_transactional_email in app.py builds
its context from exactly those keys), so a typo in a template is caught
immediately instead of surfacing as a raw "{typo}" in a sent email.
"""

from typing import Any, Dict, NamedTuple


class EmailTemplate(NamedTuple):
    subject: str
    html: str


EMAIL_TEMPLATES: Dict[str, EmailTemplate] = {
    "credit_purchase": EmailTemplate(
        subject="Confirmation d'achat de crédits Vireel",
        html=(
            "<p>Bonjour,</p>"
            "<p>Nous confirmons la réception de votre paiement de <strong>{amount:.2f} €</strong> "
            "pour l'achat de <strong>{credits:.0f} crédits</strong>.</p>"
            "<p>Vos crédits sont disponibles immédiatement sur votre compte.</p>"
            "<p>Merci pour votre confiance !</p>"
            "<p>-- L'équipe Vireel</p>"
        ),
    ),
    "subscription_purchase": EmailTemplate(
        subject="Bienvenue dans votre abonnement Vireel {plan_name}",
        html=(
            "<p>Bonjour,</p>"
            "<p>Votre abonnement <strong>{plan_name}</strong> est confirmé pour un montant de "
            "<strong>{amount:.2f} €</strong>.</p>"
            "<p>Il se renouvellera automatiquement chaque mois tant qu'il reste actif ; vous pouvez "
            "le gérer à tout moment depuis les paramètres de votre compte.</p>"
            "<p>Merci de votre confiance, et bienvenue !</p>"
            "<p>-- L'équipe Vireel</p>"
        ),
    ),
    "subscription_renewal": EmailTemplate(
        subject="Renouvellement de votre abonnement Vireel {plan_name}",
        html=(
            "<p>Bonjour,</p>"
            "<p>Votre abonnement <strong>{plan_name}</strong> vient d'être renouvelé automatiquement "
            "pour un montant de <strong>{amount:.2f} €</strong>.</p>"
            "<p>Vos crédits et votre espace de stockage ont été réinitialisés pour la nouvelle période.</p>"
            "<p>-- L'équipe Vireel</p>"
        ),
    ),
    "payment_failed": EmailTemplate(
        subject="Échec du prélèvement pour votre abonnement Vireel {plan_name} -- action requise",
        html=(
            "<p>Bonjour,</p>"
            "<p>Le prélèvement de <strong>{amount:.2f} €</strong> pour le renouvellement de votre "
            "abonnement <strong>{plan_name}</strong> a échoué.</p>"
            "<p>{retry_message}</p>"
            "<p><a href=\"{update_payment_url}\">Mettre à jour mon moyen de paiement</a></p>"
            "<p>Si le prélèvement continue d'échouer, l'accès aux fonctionnalités de votre abonnement "
            "sera suspendu jusqu'à régularisation.</p>"
            "<p>-- L'équipe Vireel</p>"
        ),
    ),
}


def render_email(template_key: str, **context: Any) -> EmailTemplate:
    """Fill in a template's subject/html from context. Raises KeyError on an
    unknown template_key, and (via str.format) on a context missing a
    placeholder the template actually uses -- both fail loudly rather than
    silently sending a broken email."""
    template = EMAIL_TEMPLATES[template_key]
    return EmailTemplate(
        subject=template.subject.format(**context),
        html=template.html.format(**context),
    )
