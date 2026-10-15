#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adaptador mínimo do Discord para o bot de rascunho.

Fluxo:
  1. Alguém da equipe, no canal de entrada, escreve:  !rascunho <mensagem do eleitor>
  2. O bot gera o rascunho (nucleo.py) e o publica no canal de revisão, com botões
     Aprovar / Rejeitar.
  3. Só quem está em APROVADORES consegue decidir; quem pediu não aprova o próprio pedido.
  4. Aprovado, o bot avisa: "copie e envie pelo canal oficial". O bot NUNCA envia nada
     ao eleitor. O envio é humano.

Por que o envio é do código e não do modelo: num sistema anterior, o agente redigia a
resposta e esquecia de chamar a ferramenta de envio; do lado de fora o bot parecia mudo.
Aqui o modelo só produz texto; publicar no canal de revisão é uma linha de código
determinística, que não tem como ser "esquecida".

Configuração só por variável de ambiente (ver ops/.env.example). Nenhum token no código.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import nucleo  # noqa: E402


def _exigir(nome: str) -> str:
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise SystemExit(f"variável de ambiente obrigatória ausente: {nome}")
    return valor


def main() -> None:
    import discord  # import tardio: py_compile e o demo não precisam da biblioteca

    token = _exigir("DISCORD_BOT_TOKEN")
    canal_entrada = int(_exigir("CANAL_ENTRADA_ID"))
    canal_revisao = int(_exigir("CANAL_REVISAO_ID"))
    aprovadores = [a.strip() for a in _exigir("APROVADORES").split(",") if a.strip()]
    pasta_base = os.environ.get("BASE_DIR", str(AQUI.parents[1] / "exemplos" / "base-helena"))
    persona_arq = os.environ.get("PERSONA", str(AQUI.parents[1] / "agentes" / "atendimento.md"))
    camada_max = os.environ.get("CAMADA_MAX", "N1")
    trilha = os.environ.get("TRILHA_AUDITORIA", str(Path.home() / "logs" / "auditoria_rascunhos.jsonl"))

    config = json.loads((AQUI / "escalacao.json").read_text(encoding="utf-8"))
    regras = nucleo.RegrasEscalacao(gatilhos=config["gatilhos"])
    proibidos = config.get("termos_proibidos_na_saida", [])
    base = nucleo.carregar_base(pasta_base, camada_max)
    system_prompt = nucleo.montar_system_prompt(Path(persona_arq).read_text(encoding="utf-8"), base)
    gerar = nucleo.gerador_claude()
    fila = nucleo.FilaDeAprovacao(aprovadores, trilha)

    intents = discord.Intents.default()
    intents.message_content = True
    cliente = discord.Client(intents=intents)

    class Decisao(discord.ui.View):
        def __init__(self, rid: str):
            super().__init__(timeout=None)
            self.rid = rid

        async def _decidir(self, interacao: "discord.Interaction", aprovar: bool):
            ok, msg = fila.decidir(self.rid, str(interacao.user.id), aprovar)
            if not ok:
                await interacao.response.send_message(f"Não registrado: {msg}.", ephemeral=True)
                return
            for item in self.children:
                item.disabled = True
            selo = "APROVADO" if aprovar else "REJEITADO"
            await interacao.response.edit_message(
                content=f"{interacao.message.content}\n\n**{selo}** por {interacao.user.mention}."
                        + (" Copie e envie pelo canal oficial." if aprovar else ""),
                view=self)

        @discord.ui.button(label="Aprovar", style=discord.ButtonStyle.success)
        async def aprovar(self, interacao, botao):
            await self._decidir(interacao, True)

        @discord.ui.button(label="Rejeitar", style=discord.ButtonStyle.danger)
        async def rejeitar(self, interacao, botao):
            await self._decidir(interacao, False)

    @cliente.event
    async def on_message(msg: "discord.Message"):
        if msg.author.bot or msg.channel.id != canal_entrada:
            return
        if not msg.content.startswith("!rascunho "):
            return
        pedido = msg.content[len("!rascunho "):]
        try:
            r = fila.criar(str(msg.author.id), pedido, system_prompt, gerar, regras, proibidos)
        except Exception as erro:  # o pedido nunca fica sem resposta
            await msg.reply(f"Não consegui gerar o rascunho ({type(erro).__name__}). "
                            "Avise a coordenação; nada foi enviado a ninguém.")
            return
        destino = cliente.get_channel(canal_revisao)
        view = Decisao(r.id) if r.estado == nucleo.PENDENTE else None
        await destino.send(r.para_revisao()[:1900], view=view)
        await msg.reply(f"Rascunho {r.id} enviado para revisão ({r.estado}).")

    cliente.run(token)


if __name__ == "__main__":
    main()
