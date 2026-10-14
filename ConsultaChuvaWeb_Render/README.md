# Pluvia — Consulta de Precipitação ANA (versão revisada)

Aplicação web local para o trabalho de Qualidade de Software. Inclui interface responsiva, validação, filtro, ordenação, acumulado do período, maior registro, exportação CSV e tratamento de falhas.

## Executar no Windows

1. Extraia a pasta `ConsultaChuvaWeb`.
2. Instale Python 3.10 ou superior, caso ainda não esteja instalado.
3. Dê dois cliques em `INICIAR_NO_WINDOWS.bat`.
4. O navegador abrirá em `http://127.0.0.1:8765`.
5. Mantenha a janela de terminal aberta enquanto usa o aplicativo.

Não precisa instalar bibliotecas adicionais. Para encerrar, pressione Ctrl+C na janela do terminal.

## O que foi ajustado

- O servidor tenta primeiro o endereço publicado atualmente na documentação da operação legada da ANA (`www.ana.gov.br/telemetria1ws`) e depois tenta o host antigo como fallback.
- Usa os parâmetros documentados `codEstacao`, `dataInicio` e `dataFim`.
- Limita cada tentativa a 9 segundos e mostra mensagens de erro claras.
- O resumo de precipitação considera todos os registros retornados pela consulta; o filtro da tabela afeta a exibição e a exportação.
- Inclui testes automatizados básicos de validação e leitura de XML: execute `python -m unittest test_server.py`.

## Limitação importante

A ANA anunciou a prorrogação do serviço antigo somente até 30/06/2026 e recomenda migrar para a API HidroWebService atual. Portanto, a consulta real pode continuar falhando se o serviço legado estiver indisponível. A versão atual tenta dois endereços documentados, mas não fabrica resultados: se a ANA não responder, o aplicativo informa a falha.

Documentação da API atual: https://www.ana.gov.br/hidrowebservice/swagger-ui/index.html
Solicitação de acesso: hidro@ana.gov.br (assunto: Solicitação de acesso à API).


## Hospedagem gratuita no Render

O projeto aceita a variável `PORT` e escuta em `0.0.0.0`, conforme exigido por serviços de hospedagem.

1. Envie esta pasta para um repositório GitHub.
2. No Render, escolha **New > Web Service** e conecte o repositório.
3. Runtime: **Python 3**. Build Command: `pip install -r requirements.txt`. Start Command: `python server.py`.
4. Escolha o plano **Free** e crie o serviço.
5. Abra a URL `onrender.com` fornecida pelo Render.

O plano gratuito pode suspender o serviço após 15 minutos sem acessos; a primeira abertura depois disso pode demorar cerca de um minuto. A hospedagem não resolve eventual indisponibilidade da API legada da ANA.
