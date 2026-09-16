# PRD — ZapPedidos Multi-Tenant

## Problema original
Continuar o projeto ZapPedidos enviado, transformando-o em um painel único para revenda, com painel administrativo, painel do cliente, lojas, planos, catálogo e conexão individual de WhatsApp por WAHA em uma VPS.

## Personas
- Administrador geral: controla a operação e os acessos.
- Revendedor: cadastra e acompanha lojas clientes.
- Cliente/lojista: gerencia sua própria loja, catálogo e conexão WAHA.

## Decisões de arquitetura
- React + FastAPI + MongoDB, preservando a infraestrutura existente do workspace.
- Sessão JWT em cookie httpOnly, com separação por `role` e `client_id`.
- Cada loja recebe uma sessão WAHA própria, URL/token e nome de sessão isolados.
- Tokens de integração nunca são retornados nas respostas públicas.
- Integrações WAHA não configuradas retornam estado compreensível, sem quebrar o painel.

## Requisitos implementados — 21/02/2026
- Login, logout, sessão atual e seed do administrador geral.
- Painel responsivo com visão geral, métricas e status por loja.
- Cadastro de loja + criação automática de acesso do cliente.
- Lista de lojas/clientes, planos e visão de uso.
- Catálogo de produtos por loja.
- Configuração, inicialização e teste de sessão individual WAHA.
- Isolamento de loja para o perfil cliente.
- Interface em português, com estados vazios e mensagens de erro.

## Backlog priorizado
- P0: QR Code real e polling do estado da sessão WAHA.
- P0: edição/exclusão de produtos e edição completa de loja.
- P1: cobrança e limites de planos.
- P1: webhooks de pedidos e histórico de conversas.
- P2: auditoria, convites de revendedores e relatórios.

## Próximas tarefas
1. Conectar a leitura do QR Code aos endpoints da versão WAHA instalada.
2. Adicionar CRUD completo de produtos.
3. Adicionar cobrança e controle automático de quota por plano.