import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_password_reset_email(*, recipient: str, reset_url: str) -> bool:
    """Envia o link de redefinição de senha pelo SMTP configurado."""
    if not settings.smtp_configured:
        logger.error("SMTP não configurado para recuperação de senha.")
        return False

    safe_url = escape(reset_url, quote=True)
    validity = settings.reset_token_minutes

    message = EmailMessage()
    message["Subject"] = "Redefinição de senha — FlowDeskIA"
    message["From"] = formataddr(
        (settings.smtp_from_name, settings.smtp_from or "")
    )
    message["To"] = recipient

    if settings.smtp_reply_to:
        message["Reply-To"] = settings.smtp_reply_to

    message.set_content(
        "Olá,\n\n"
        "Recebemos uma solicitação para redefinir sua senha no FlowDeskIA.\n\n"
        f"Acesse o link abaixo para criar uma nova senha:\n{reset_url}\n\n"
        f"Este link é válido por {validity} minutos e pode ser usado apenas uma vez.\n\n"
        "Caso você não tenha solicitado a redefinição, ignore esta mensagem. "
        "Sua senha continuará a mesma.\n\n"
        "Equipe FlowDeskIA"
    )

    message.add_alternative(
        f"""
        <!doctype html>
        <html lang="pt-BR">
          <body style="margin:0;background:#f4f7fb;font-family:Arial,sans-serif;color:#172033;">
            <div style="padding:32px 16px;">
              <div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #dfe6f0;border-radius:18px;overflow:hidden;">
                <div style="padding:26px 30px;background:#11203d;color:#ffffff;">
                  <div style="display:inline-block;padding:9px 13px;border-radius:10px;background:#3157d5;font-size:20px;font-weight:800;">F</div>
                  <div style="display:inline-block;margin-left:10px;vertical-align:middle;font-size:19px;font-weight:800;">FlowDeskIA</div>
                </div>

                <div style="padding:32px 30px;">
                  <p style="margin:0 0 8px;color:#3157d5;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;">Segurança da conta</p>
                  <h1 style="margin:0 0 16px;font-size:26px;">Redefinição de senha</h1>
                  <p style="margin:0 0 22px;color:#5f6d85;line-height:1.6;">
                    Recebemos uma solicitação para redefinir sua senha. Clique no botão abaixo para criar uma nova senha.
                  </p>

                  <p style="margin:0 0 24px;">
                    <a href="{safe_url}" style="display:inline-block;padding:13px 20px;border-radius:10px;background:#3157d5;color:#ffffff;text-decoration:none;font-weight:800;">
                      Redefinir minha senha
                    </a>
                  </p>

                  <p style="margin:0 0 12px;color:#5f6d85;font-size:14px;line-height:1.6;">
                    O link é válido por <strong>{validity} minutos</strong> e pode ser usado somente uma vez.
                  </p>
                  <p style="margin:0;color:#7b879b;font-size:13px;line-height:1.6;">
                    Caso você não tenha solicitado esta alteração, ignore a mensagem. Sua senha permanecerá inalterada.
                  </p>
                </div>

                <div style="padding:18px 30px;border-top:1px solid #e5eaf2;color:#8a95a8;font-size:12px;">
                  Este é um e-mail automático do FlowDeskIA.
                </div>
              </div>
            </div>
          </body>
        </html>
        """,
        subtype="html",
    )

    context = ssl.create_default_context()

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
                context=context,
            ) as server:
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as server:
                server.ehlo()
                if settings.smtp_starttls:
                    server.starttls(context=context)
                    server.ehlo()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)

        logger.info("E-mail de recuperação enviado para %s.", recipient)
        return True
    except Exception:
        logger.exception("Não foi possível enviar o e-mail de recuperação.")
        return False
