# Integração Omie ERP — Documentação de Recursos da API

Documentação dos recursos disponíveis na área de desenvolvedor da Omie
([Portal do Desenvolvedor](https://developer.omie.com.br/)), levantada como base
para o projeto de integração.

> Conteúdo baseado na análise da [Lista de APIs do Portal do Desenvolvedor Omie](https://developer.omie.com.br/service-list/)
> e artigos da Central de Ajuda Omie. Conteúdo reescrito e organizado para fins de
> documentação interna do projeto.

## Sumário

A documentação detalhada fica na pasta [`docs-erp-omie/`](./docs-erp-omie/).

| Documento | Conteúdo |
|-----------|----------|
| [docs-erp-omie/01-visao-geral.md](./docs-erp-omie/01-visao-geral.md) | Visão geral do portal, protocolos suportados e conceitos |
| [docs-erp-omie/02-autenticacao-e-requisicoes.md](./docs-erp-omie/02-autenticacao-e-requisicoes.md) | Autenticação (app_key/app_secret), formato de requisição e resposta |
| [docs-erp-omie/03-modulos-e-servicos.md](./docs-erp-omie/03-modulos-e-servicos.md) | Catálogo completo de módulos e serviços disponíveis |
| [docs-erp-omie/04-boas-praticas.md](./docs-erp-omie/04-boas-praticas.md) | Boas práticas de integração (paginação, listagem incremental, rate limit) |
| [docs-erp-omie/05-exemplos-de-uso.md](./docs-erp-omie/05-exemplos-de-uso.md) | Exemplos práticos de chamadas (cURL, Python, PHP) |

## Conciliador OFX → Omie

Além da documentação da API, este repositório contém um **conciliador** em
Python (`conciliador-ofx/`) que lê um extrato OFX, aplica regras de roteamento e
gera um relatório das ações que seriam executadas no Omie. Ele roda em
**dry-run** (somente leitura): nunca executa inclusão, baixa ou manutenção.

- **Como executar o fluxo:** [`conciliador-ofx/COMO-EXECUTAR.md`](./conciliador-ofx/COMO-EXECUTAR.md)
  — pré-requisitos, configuração de credenciais (`.env`), execução e saída.

A análise dos endpoints e as coleções para importar no Apidog ficam em
[`proposta-conciliacao-ofx/`](./proposta-conciliacao-ofx/).

## Resumo rápido

- **Tipo de API:** REST sobre HTTP, com payload JSON (também há suporte a SOAP/WSDL).
- **Endpoint base:** `https://app.omie.com.br/api/v1/<modulo>/<recurso>/`
- **Autenticação:** `app_key` + `app_secret` enviados no corpo de cada requisição.
- **Versão atual dos serviços:** `v1`.
- **Módulos principais:** Geral, CRM, Finanças, Compras/Estoque/Produção,
  Vendas e NF-e, Serviços e NFS-e, Painel do Contador.

## Como as credenciais são obtidas

As credenciais (`app_key` e `app_secret`) são geradas dentro do próprio Omie ao
cadastrar um aplicativo/integração. Cada aplicativo tem seu próprio par de chaves,
o que permite controlar e auditar o consumo por integração.
