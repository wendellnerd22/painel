# ZapPedidos — roteiro de autenticação

1. Acesse `POST /api/auth/login` com o administrador informado em `memory/test_credentials.md`.
2. Confirme o cookie `zp_session` e consulte `GET /api/auth/me`.
3. Teste `POST /api/auth/logout` e confirme que `/api/auth/me` retorna 401.
4. Após novo login, consulte `/api/dashboard`, crie uma loja e valide o usuário cliente.
5. O token Waha nunca é retornado pelas rotas públicas; ele é usado somente no backend.