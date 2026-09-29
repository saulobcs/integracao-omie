# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Alterado
- Roteamento e plano de contas agora são **isolados por cliente**
  (`clientes/<id>/roteamento.json` e `clientes/<id>/contas-haru.json`), em vez
  de um `config/roteamento.json` global. Esses arquivos carregam IDs do Omie
  (`nCodCC`/`cCodCateg`) específicos de cada cliente.
- `clientes.json` do perfil `haru` atualizado para os novos caminhos.

### Adicionado
- Validação que impede dois clientes de compartilharem o mesmo arquivo de
  roteamento ou de plano de contas (evita rotear lançamentos para contas de
  outro cliente).

## [0.1.0] - 2026-09-29

Primeira versão marcada do conciliador OFX → Omie.

### Adicionado
- Conciliador OFX → Omie em Python (stdlib), com parser tolerante de OFX SGML
  (`VERSION:102`, tags sem fechamento).
- Três modos de execução: `offline` (sem API), `dry-run` (consulta read-only
  para idempotência/matching) e `apply` (escrita real no Omie, com confirmação
  obrigatória).
- Motor de regras de roteamento por conta de origem (`config/roteamento.json`),
  incluindo regras da Stone para recebimento de vendas (débito) e iFood.
- Matching de débito com consulta read-only à API Omie e checagem de
  idempotência via `ConsultaLancCC`/`ListarLancCC` antes de incluir.
- Derivação de `cCodIntLanc` a partir do FITID.
- Suporte multi-cliente com perfis isolados por cliente e salvaguardas
  (validação de BANKID/ACCTID do extrato contra o perfil selecionado).
- Interface web local (`conciliador_web.py`) restrita a `127.0.0.1`, expondo
  apenas os modos seguros (offline e dry-run).
- Relatórios de saída em CSV, JSON e HTML.
- Instaladores por sistema com auto-instalação do Python.
- Flag `--version` na CLI e versão central em `conciliador.__version__`.

### Documentação
- Documentação dos recursos da API Omie (`docs-erp-omie/`).
- Guia de execução do conciliador (`conciliador-ofx/COMO-EXECUTAR.md`).
- Proposta e análise de endpoints/roteamento (`proposta-conciliacao-ofx/`).

[Não lançado]: https://github.com/saulobcs/integracao-omie/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/saulobcs/integracao-omie/releases/tag/v0.1.0
