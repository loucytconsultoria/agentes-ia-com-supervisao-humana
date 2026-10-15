#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Operação de contatos do funil (CRM no ClickUp) com as travas que um agente precisa.

É a ÚNICA ferramenta de gravação que o agente operador-crm pode chamar.

Travas:
  1. Simulação por padrão. Nada é gravado sem --aplicar.
  2. Busca de duplicata em TODAS as listas do funil antes de inserir, por igualdade
     exata de e-mail, telefone (só dígitos) ou nome normalizado. Sem "parecido":
     se apontou, é sinal forte.
  3. Duplicata comum bloqueia a inserção, a menos que o humano diga que é outra pessoa
     (--forcar).
  4. Contato na lista de BLOQUEIO não é duplicata, é parada: --forcar não destrava.
     Quem pediu para não ser contatado só volta por decisão da coordenação (LGPD).
  5. Um contato por chamada. Não apaga, não mescla, não faz lote.

Uso:
    python operar_contato.py buscar  --nome "..." [--telefone ...] [--email ...]
    python operar_contato.py inserir --nome "..." [--telefone ...] [--email ...] [--municipio ...] [--lista leads] [--forcar] [--aplicar]
    python operar_contato.py editar  --id <task_id> [--telefone ...] [--status ...] [--aplicar]
    Acrescente --offline exemplos/crm_ficticio.json para rodar sem API (demonstração).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import clickup_client as cc  # noqa: E402


# ---------------------------------------------------------------------------
# Normalização (igualdade exata depois de normalizar; nada de semelhança)
# ---------------------------------------------------------------------------
def norm_nome(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def norm_tel(s: str) -> str:
    d = re.sub(r"\D", "", s or "")
    return d[2:] if d.startswith("55") and len(d) > 11 else d


def norm_email(s: str) -> str:
    return (s or "").strip().lower()


# ---------------------------------------------------------------------------
# Fonte dos contatos: offline (arquivo) ou API
# ---------------------------------------------------------------------------
def contatos_offline(caminho: str) -> dict[str, list[dict]]:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))["listas"]


def contatos_api(cfg: dict) -> dict[str, list[dict]]:
    campos = cfg["funil"]["campos"]
    saida = {}
    for apelido in cfg["funil"]["listas_busca"]:
        lista_id = cc.resolver_lista(apelido, cfg)
        itens = []
        for t in cc.get_all_tasks(lista_id):
            valores = {f["id"]: f.get("value") for f in t.get("custom_fields", [])}
            itens.append({"id": t["id"], "nome": t["name"],
                          "telefone": valores.get(campos.get("telefone")) or "",
                          "email": valores.get(campos.get("email")) or ""})
        saida[apelido] = itens
    return saida


def buscar(listas: dict[str, list[dict]], nome="", telefone="", email="") -> list[dict]:
    alvo = {"nome": norm_nome(nome), "telefone": norm_tel(telefone), "email": norm_email(email)}
    achados = []
    for apelido, itens in listas.items():
        for c in itens:
            motivos = []
            if alvo["email"] and norm_email(c.get("email")) == alvo["email"]:
                motivos.append("e-mail igual")
            if alvo["telefone"] and norm_tel(c.get("telefone")) == alvo["telefone"]:
                motivos.append("telefone igual")
            if alvo["nome"] and norm_nome(c.get("nome")) == alvo["nome"]:
                motivos.append("nome igual")
            if motivos:
                achados.append({"lista": apelido, "id": c.get("id"), "nome": c.get("nome"),
                                "motivo": ", ".join(motivos)})
    return achados


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
def cmd_inserir(a, cfg, listas) -> int:
    bloqueio = cfg["funil"]["lista_bloqueio"]
    achados = buscar(listas, a.nome, a.telefone, a.email)
    em_bloqueio = [x for x in achados if x["lista"] == bloqueio]
    comuns = [x for x in achados if x["lista"] != bloqueio]
    lista = a.lista or cfg["funil"]["lista_padrao_insercao"]
    plano = {"acao": "inserir", "lista": lista,
             "campos": {k: v for k, v in {"nome": a.nome, "telefone": a.telefone, "email": a.email,
                                          "municipio": a.municipio}.items() if v},
             "duplicatas": comuns, "bloqueio": em_bloqueio}
    print(json.dumps(plano, ensure_ascii=False, indent=2))

    if em_bloqueio:
        print("\nPARADA: contato consta na lista de bloqueio. Não é possível cadastrar por cima."
              "\n[ESCALAR: contato em lista de bloqueio] Só a coordenação reverte.")
        return 3
    if comuns and not a.forcar:
        print("\nDUPLICATA: há contato com dado igual. Confirme com o gestor se é outra pessoa;"
              " só então repita com --forcar.")
        return 2
    if not a.aplicar:
        print("\n>>> simulação: nada foi gravado. Mostre o plano ao gestor e, com confirmação"
              " explícita, repita com --aplicar.")
        return 0
    if a.offline:
        print("\n(modo offline: a gravação seria feita aqui)")
        return 0
    campos = cfg["funil"]["campos"]
    custom = [{"id": campos[k], "value": v} for k, v in
              (("telefone", a.telefone), ("email", a.email), ("municipio", a.municipio)) if v and campos.get(k)]
    r = cc.criar_tarefa(cc.resolver_lista(lista, cfg), {"name": a.nome, "custom_fields": custom}, aplicar=True)
    print(json.dumps({"gravado": True, "id": r["resultado"].get("id"), "url": r["resultado"].get("url")},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_editar(a, cfg) -> int:
    mudancas = {k: v for k, v in {"telefone": a.telefone, "email": a.email,
                                  "municipio": a.municipio, "status": a.status}.items() if v}
    if not mudancas:
        print("nada para editar: informe ao menos um campo")
        return 1
    print(json.dumps({"acao": "editar", "id": a.id, "mudancas": mudancas}, ensure_ascii=False, indent=2))
    if not a.aplicar:
        print("\n>>> simulação: nada foi gravado. Com confirmação explícita, repita com --aplicar.")
        return 0
    if a.offline:
        print("\n(modo offline: a gravação seria feita aqui)")
        return 0
    campos = cfg["funil"]["campos"]
    if "status" in mudancas:
        cc.atualizar_tarefa(a.id, {"status": mudancas.pop("status")}, aplicar=True)
    for k, v in mudancas.items():
        if campos.get(k):
            cc.definir_campo(a.id, campos[k], v, aplicar=True)
    print(json.dumps({"gravado": True, "id": a.id}, ensure_ascii=False))
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Operação segura de contatos do funil")
    ap.add_argument("comando", choices=["buscar", "inserir", "editar"])
    ap.add_argument("--nome", default=""); ap.add_argument("--telefone", default="")
    ap.add_argument("--email", default=""); ap.add_argument("--municipio", default="")
    ap.add_argument("--status", default=""); ap.add_argument("--id", default="")
    ap.add_argument("--lista", default="")
    ap.add_argument("--forcar", action="store_true", help="o gestor confirmou que é outra pessoa")
    ap.add_argument("--aplicar", action="store_true", help="grava de verdade")
    ap.add_argument("--offline", default="", help="arquivo JSON fictício no lugar da API")
    ap.add_argument("--config", default="", help="config do funil (padrão: CLICKUP_CONFIG)")
    a = ap.parse_args()

    if a.offline:
        cfg = {"funil": {"listas_busca": [], "lista_bloqueio": "bloqueio",
                         "lista_padrao_insercao": "leads", "campos": {}}}
        listas = contatos_offline(a.offline)
    else:
        cfg = cc.carregar_config(a.config or None)
        if not cfg.get("funil"):
            print("config do funil ausente (veja config.exemplo.json)")
            return 1
        listas = None

    if a.comando == "buscar":
        listas = listas if listas is not None else contatos_api(cfg)
        print(json.dumps(buscar(listas, a.nome, a.telefone, a.email), ensure_ascii=False, indent=2))
        return 0
    if a.comando == "inserir":
        if not a.nome:
            print("informe ao menos --nome")
            return 1
        return cmd_inserir(a, cfg, listas if listas is not None else contatos_api(cfg))
    if not a.id:
        print("informe --id da tarefa a editar")
        return 1
    return cmd_editar(a, cfg)


if __name__ == "__main__":
    sys.exit(main())
