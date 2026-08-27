# 04 — Boas Práticas de Integração

Recomendações baseadas no guia oficial de
[Boas Práticas de Integração com as APIs do Omie](https://ajuda.omie.com.br/pt-BR/articles/12607801-boas-praticas-de-integracao-com-as-apis-do-omie).

## 1. Prefira listagens incrementais

Ao sincronizar dados, use os métodos de **listagem em lote** (`Listar*`) em vez de
consultas individuais, e informe sempre a **data/hora da última sincronização**.

Assim, apenas registros novos ou alterados após aquela data/hora são retornados,
o que reduz drasticamente o volume de dados trafegados e o número de chamadas.

- Guarde o timestamp da última sincronização bem-sucedida por recurso.
- Filtre as próximas listagens por esse timestamp (parâmetros de data de
  criação/alteração variam por recurso).

## 2. Pagine os resultados

- Limite a **no máximo 100 registros por página** (`registros_por_pagina`) nas
  listagens em lote.
- Ajuste o volume conforme o recurso: para Contas a Receber faz sentido buscar
  volumes maiores; para Contas Correntes, volumes menores.
- Adotar 100 registros como padrão para todas as APIs é uma escolha segura.
- Percorra todas as páginas usando `total_de_paginas` retornado na resposta.

## 3. Trate erros e controle o consumo

- Implemente **retry com backoff** (idealmente exponencial) para falhas transitórias.
- Respeite os **limites de rate limit** do Omie; evite rajadas de requisições.
- **Inspecione o corpo da resposta** para detectar erros de negócio, pois a API
  pode retornar mensagens de falha mesmo com status HTTP não-2xx.
- Diferencie: erro de credencial/autorização, erro de parâmetro e erro de negócio.

## 4. Garanta o documento de origem

Toda informação registrada na aplicação integrada deve gerar um **pedido ou
documento de origem** no Omie, que será faturado/concluído e só então gerará o
lançamento financeiro.

- **Evite** criar lançamentos financeiros diretamente quando existe um documento
  de origem que deveria ser gerado antes.
- Lançar de forma antecipada ou paralela pode causar duplicidade de registros,
  bloqueio do faturamento do documento fiscal e lançamentos contábeis/fiscais indevidos.

## 5. Segurança de credenciais

- Nunca versione `app_key`/`app_secret` no repositório.
- Use variáveis de ambiente ou um cofre de segredos.
- Prefira uma credencial por integração para isolar consumo e permitir revogação
  granular.

## 6. Idempotência e reprocessamento

- Ao incluir registros, guarde o identificador retornado pelo Omie (ex.:
  `codigo_cliente_omie`) para evitar duplicações em reprocessamentos.
- Quando disponível, use o código de integração próprio (campo de "código de
  integração" que muitos recursos aceitam) para correlacionar registros entre
  os sistemas e viabilizar operações de upsert.

## Referências

- [Boas Práticas de Integração com as APIs do Omie](https://ajuda.omie.com.br/pt-BR/articles/12607801-boas-praticas-de-integracao-com-as-apis-do-omie)

_Conteúdo reescrito para fins de documentação interna._
