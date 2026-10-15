#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Envia um aviso do monitor. Canal primário: e-mail (SMTP). Reserva: webhook de chat,
que só dispara se o e-mail falhar, e diz no texto que o e-mail falhou.

Por que e-mail e não o próprio canal de chat dos agentes: avisos postados no mesmo
lugar onde os agentes conversam se perdem no meio das conversas e não viram ação.
Por que nada aqui passa pelo modelo: a pane mais importante é o modelo parar.

Configuração só por ambiente (ver ops/.env.example):
    ALERTA_EMAIL_PARA      destinatários separados por vírgula
    SMTP_HOST, SMTP_PORT, SMTP_USUARIO, SMTP_APP_PASSWORD
    ALERTA_REMETENTE_NOME  (opcional)
    ALERTA_WEBHOOK_URL     (opcional) webhook que aceita JSON {"content": "..."}
    ALERTA_PREFIXO         (opcional) prefixo do assunto, padrão "[AGENTES]"

Uso:
    python3 alerta.py "texto do aviso"
    python3 alerta.py --testar
    python3 alerta.py --simular "texto"     # mostra assunto e destino, não envia
"""
import json
import os
import smtplib
import ssl
import sys
import urllib.request
from email.message import EmailMessage

PREFIXO = os.environ.get("ALERTA_PREFIXO", "[AGENTES]")

# (trecho no texto, gravidade, rótulo). Ordem importa: o primeiro que casar vence.
CLASSES = [
    ("tudo no ar", "", "Agentes ok"),
    ("com problema", "ATENÇÃO", "pulso diário com problema"),
    ("login do modelo", "CRÍTICO", "login do modelo caiu"),
    ("mudo", "CRÍTICO", "os agentes estão MUDOS"),
    ("fora do ar", "CRÍTICO", "agente fora do ar"),
    ("mensagem parada", "", "agente com mensagem parada"),
    ("voltou sozinho", "", "agente caiu e voltou sozinho"),
    ("pontes", "", "ponte com o canal de chat caiu"),
    ("menu de limite", "", "agente preso no menu de limite"),
]


def assunto_de(texto: str) -> str:
    t = texto.lower()
    for trecho, gravidade, rotulo in CLASSES:
        if trecho in t:
            return f"{PREFIXO} {gravidade + ': ' if gravidade else ''}{rotulo}"
    return f"{PREFIXO} Aviso do monitor"


def destinatarios() -> list:
    return [e.strip() for e in os.environ.get("ALERTA_EMAIL_PARA", "").split(",") if e.strip()]


def por_email(texto: str):
    para = destinatarios()
    usuario = os.environ.get("SMTP_USUARIO", "").strip()
    senha = os.environ.get("SMTP_APP_PASSWORD", "").strip()
    if not (para and usuario and senha):
        return False, "configuração de e-mail incompleta no ambiente"
    msg = EmailMessage()
    msg["Subject"] = assunto_de(texto)
    msg["From"] = f"{os.environ.get('ALERTA_REMETENTE_NOME', 'Monitor dos agentes')} <{usuario}>"
    msg["To"] = ", ".join(para)
    msg.set_content(texto + "\n\n---\nEnviado pelo monitor do servidor dos agentes.\n")
    try:
        host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        porta = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(host, porta, timeout=30) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(usuario, senha)
            s.send_message(msg)
        return True, f"e-mail enviado a {len(para)} destinatário(s)"
    except Exception as erro:
        return False, f"falha no e-mail: {type(erro).__name__}"


def por_webhook(texto: str):
    url = os.environ.get("ALERTA_WEBHOOK_URL", "").strip()
    if not url:
        return False, "sem webhook de reserva configurado"
    try:
        req = urllib.request.Request(
            url, data=json.dumps({"content": texto[:1900]}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=20).close()
        return True, "aviso enviado pelo webhook de reserva"
    except Exception as erro:
        return False, f"falha no webhook: {type(erro).__name__}"


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["--simular"]:
        texto = " ".join(args[1:]).strip()
        print(json.dumps({"assunto": assunto_de(texto), "para": destinatarios(),
                          "reserva": bool(os.environ.get("ALERTA_WEBHOOK_URL"))},
                         ensure_ascii=False))
        return
    texto = ("MONITOR: teste do canal de aviso. Se chegou, os avisos do monitor caem aqui."
             if args[:1] == ["--testar"] else " ".join(args).strip())
    if not texto:
        raise SystemExit("uso: alerta.py <mensagem> | --testar | --simular <mensagem>")
    ok, detalhe = por_email(texto)
    print(detalhe)
    if ok:
        return
    ok2, detalhe2 = por_webhook(f"[o e-mail do monitor falhou: {detalhe}]\n\n{texto}")
    print(detalhe2)
    if not ok2:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
