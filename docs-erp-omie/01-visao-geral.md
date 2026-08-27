# 01 — Visão Geral

## O que é o Portal do Desenvolvedor Omie

O [Portal do Desenvolvedor Omie](https://developer.omie.com.br/) centraliza a
documentação de todas as APIs de integração do ERP. A partir dele é possível:

- Consultar a lista de módulos/serviços disponíveis (agrupados por área de negócio).
- Ver a documentação de cada método (parâmetros de requisição e resposta).
- Configurar a URL de consumo em JSON, PHP SOAP ou WSDL.
- Testar métodos diretamente na página ("Teste agora mesmo"), selecionando o
  aplicativo de origem e ajustando o corpo da requisição.

## Protocolos suportados

As APIs podem ser consumidas de duas formas:

- **JSON sobre HTTP (REST)** — abordagem recomendada e mais comum.
- **SOAP / WSDL** — para clientes que precisam de contrato formal ou já usam stacks SOAP.

Este projeto adota o consumo via **JSON/HTTP**.

## Modelo de endpoints

Cada serviço tem um endpoint próprio no padrão:

```
https://app.omie.com.br/api/v1/<modulo>/<recurso>/
```

Exemplos:

| Recurso | Endpoint |
|---------|----------|
| Clientes | `https://app.omie.com.br/api/v1/geral/clientes/` |
| Produtos | `https://app.omie.com.br/api/v1/geral/produtos/` |
| Contas a Pagar | `https://app.omie.com.br/api/v1/financas/contapagar/` |
| Contas a Receber | `https://app.omie.com.br/api/v1/financas/contareceber/` |
| Pedidos de Venda | `https://app.omie.com.br/api/v1/produtos/pedido/` |

Diferente de APIs REST tradicionais, a Omie **não** usa verbos HTTP diferentes
(GET/POST/PUT/DELETE) para diferenciar operações. Em vez disso:

- Todas as chamadas são feitas via **POST** (JSON no body) para o endpoint do recurso.
- A **operação desejada** é identificada pelo campo `call` no corpo da requisição
  (ex.: `ListarClientes`, `IncluirCliente`, `AlterarCliente`, `ConsultarCliente`).

## Conceitos importantes

- **`call`** — nome do método a executar dentro do recurso.
- **`param`** — array com os parâmetros específicos do método.
- **Listagem em lote vs. consulta** — métodos `Listar*` retornam múltiplos
  registros com paginação; métodos `Consultar*` retornam um único registro.
- **Documento de origem** — no fluxo operacional, lançamentos financeiros devem
  derivar de um pedido/documento gerado no Omie, e não ser criados isoladamente.

## Referências

- [Portal do Desenvolvedor](https://developer.omie.com.br/)
- [Lista de APIs](https://developer.omie.com.br/service-list/)
- [Acessando a documentação e testando as APIs](https://ajuda.omie.com.br/pt-BR/articles/5412731-acessando-a-documentacao-e-testando-as-apis)

_Conteúdo reescrito para fins de documentação interna._
