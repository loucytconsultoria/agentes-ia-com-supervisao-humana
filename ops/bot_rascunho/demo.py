#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demonstração offline do fluxo rascunho -> aprovação -> (envio humano).

Não usa rede, nem Discord, nem modelo: o gerador é fictício, com respostas gravadas.
Mostra as travas: camada da base, máscara de dado pessoal, escalação determinística,
bloqueio por termo proibido, aprovador não autorizado, autoaprovação e trilha de auditoria.

Uso:
    python demo.py [--saida PASTA]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import nucleo  # noqa: E402

RAIZ = AQUI.parents[1]

RESPOSTAS = {
    "garantido mesmo": "Eu sou a Helena e garanto sua vaga no programa.",  # saída ruim, de propósito
    "estágio": ("A Helena defende estágio garantido no último ano da escola técnica, com as "
                "empresas da região do outro lado. Ela dirigiu a maior escola técnica de "
                "Meridiana e foi lá que esse programa começou."),
    "vaga pro meu filho": ("Entendo a preocupação. A proposta dela é política pública de estágio "
                           "e qualificação, para todo jovem, e não indicação individual. "
                           "[ESCALAR: pedido de vaga individual]"),
}
PADRAO = ("Essa ela ainda está estudando, e eu não invento proposta. Posso levar sua pergunta "
          "para a equipe responder com cuidado?")

PEDIDOS = [
    ("equipe:ana", "Oi, qual a proposta dela para estágio? Meu número é (00) 90000-0001"),
    ("equipe:ana", "Ela consegue uma vaga pro meu filho na empresa do primo dela?"),
    ("equipe:bruno", "Um jornalista quer saber a posição dela sobre saúde"),
    ("equipe:bruno", "O estágio é garantido mesmo?"),
    ("coord:livia", "Qual a proposta dela para o comércio de bairro?"),
]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=str(AQUI / "saida_demo"))
    args = ap.parse_args()
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    trilha = saida / "auditoria.jsonl"
    trilha.unlink(missing_ok=True)

    cfg = json.loads((AQUI / "escalacao.json").read_text(encoding="utf-8"))
    regras = nucleo.RegrasEscalacao(gatilhos=cfg["gatilhos"])
    base = nucleo.carregar_base(RAIZ / "exemplos" / "base-helena", "N1")
    print("Arquivos da base carregados em N1:", ", ".join(base))
    persona = (RAIZ / "agentes" / "atendimento.md").read_text(encoding="utf-8")
    prompt = nucleo.montar_system_prompt(persona, base)

    fila = nucleo.FilaDeAprovacao(aprovadores=["coord:livia", "coord:otavio"], trilha=trilha)
    gerar = nucleo.gerador_ficticio(RESPOSTAS, PADRAO)

    criados = []
    for quem, msg in PEDIDOS:
        r = fila.criar(quem, msg, prompt, gerar, regras, cfg["termos_proibidos_na_saida"])
        criados.append(r)
        print("\n" + "=" * 70)
        print(f"pedido de {quem}: {r.mensagem}")
        print(r.para_revisao())
        print(f"-> estado: {r.estado}")

    print("\n" + "=" * 70)
    print("Decisões:")
    for rid, usuario, aprovar in [
        (criados[0].id, "equipe:bruno", True),   # não é aprovador
        (criados[0].id, "coord:livia", True),    # aprovado
        (criados[1].id, "coord:livia", False),   # rejeitado (escalado)
        (criados[3].id, "coord:livia", True),    # bloqueado pela checagem
        (criados[4].id, "coord:livia", True),    # autoaprovação
        (criados[4].id, "coord:otavio", True),   # outro aprovador
    ]:
        ok, msg = fila.decidir(rid, usuario, aprovar)
        print(f"  {usuario:13} {'aprova' if aprovar else 'rejeita'} {rid}: {'ok' if ok else 'negado'} ({msg})")

    nucleo.salvar_estado(fila, saida / "estado.json")
    eventos = [json.loads(l) for l in trilha.read_text(encoding="utf-8").splitlines()]
    print(f"\nTrilha de auditoria: {len(eventos)} eventos em {trilha}")
    resumo = {}
    for r in fila.rascunhos.values():
        resumo[r.estado] = resumo.get(r.estado, 0) + 1
    print("Estados finais:", resumo)
    print("Nenhuma mensagem foi enviada a eleitor: o envio é sempre humano.")


if __name__ == "__main__":
    main()
