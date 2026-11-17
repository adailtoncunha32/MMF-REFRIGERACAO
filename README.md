# ❄️ Técnicos AVAC Pro

Plataforma interna de recrutamento e prospeção de técnicos de AVAC, climatização, refrigeração,
aquecimento e energias renováveis, focada em Lisboa e arredores.

## Guia rápido — três passos

```
1. Criar o ambiente virtual e instalar as dependências.
2. Configurar as chaves da Anthropic e da Tavily.
3. Executar: streamlit run app.py
```

## Publicação na Internet (gratuita)

A aplicação é um servidor Python (Streamlit). O Firebase Hosting só serve sites estáticos e não
suporta as ligações WebSocket de que o Streamlit precisa, por isso a publicação gratuita é feita com:

- **Streamlit Community Cloud** — alojamento gratuito, com endereço `https://<nome>.streamlit.app`.
- **Supabase** (ou Neon) — base de dados PostgreSQL gratuita. É obrigatória: o disco do alojamento
  é apagado a cada reinício, pelo que o SQLite local perderia os dados.

### Passo 1 — Base de dados (Supabase)

1. Crie um projeto em <https://supabase.com> (plano Free) e guarde a palavra-passe da base de dados.
2. No projeto, clique em **Connect** e copie a ligação **Session pooler** (começa por
   `postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-…pooler.supabase.com:5432/postgres`).
   Use o *Session pooler* e não a *Direct connection*, que só funciona em IPv6.
3. Substitua `[YOUR-PASSWORD]` pela palavra-passe. As tabelas são criadas sozinhas no primeiro arranque.

### Passo 2 — Alojamento (Streamlit Community Cloud)

1. Entre em <https://share.streamlit.io> com a conta do GitHub.
2. **Create app → Deploy a public app from GitHub**: escolha este repositório, ramo `main`,
   ficheiro principal `app.py`, e defina o endereço pretendido (ex.: `mmf-tecnicos`).
3. Em **Advanced settings → Secrets**, cole (com os seus valores):

   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   TAVILY_API_KEY = "tvly-..."
   DATABASE_URL = "postgresql://postgres.xxxx:PALAVRA-PASSE@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
   ADMIN_NOME = "Nome do responsável"
   ADMIN_EMAIL = "responsavel@empresa.pt"
   ADMIN_PASSWORD = "PalavraPasseForte2026"
   ```

4. Clique em **Deploy**. Não existe registo público: o primeiro administrador é criado
   automaticamente com o `ADMIN_EMAIL` e a `ADMIN_PASSWORD` dos Secrets. Sem esses valores, a página
   inicial apenas avisa que a aplicação não está configurada. Os restantes utilizadores são criados
   por um administrador em **Administração → Utilizadores**.

As chaves ficam guardadas apenas nos *Secrets* do alojamento: não estão no repositório nem são
mostradas aos utilizadores. Cada nova versão enviada para o GitHub é publicada automaticamente.

### Onde obter a chave da Tavily

Registe-se em <https://app.tavily.com>; a chave (`tvly-…`) aparece no painel inicial. O plano
gratuito inclui créditos mensais suficientes para dezenas de prospeções (cada uma gasta cerca de
12 a 20 créditos).

## Objetivo da aplicação

Permitir à empresa encontrar rapidamente profissionais disponíveis, avaliar os perfis com
Inteligência Artificial, contactá-los e acompanhar o processo até à contratação:

- Pesquisa de profissionais por especialidade, localização, raio e disponibilidade.
- Prospeção em fontes públicas (Tavily) e análise dos perfis pela IA (Anthropic Claude).
- A IA limita-se a identificar profissionais (técnicos e engenheiros) e a registar os dados, com um
  score e um resumo curto. O contacto é feito diretamente pelos administradores.
- Base de dados única, sem duplicados, com estados, notas, tarefas, entrevistas e contratações.
- Modo de **pesquisa urgente** para necessidades imediatas.
- Exportação para CSV, Excel e PDF.
- Três perfis de utilizador: Administrador, Recrutador e Gestor.

## Arquitetura

| Ficheiro | Responsabilidade |
|---|---|
| `app.py` | Interface Streamlit: autenticação, barra lateral, dashboard, candidatos, pesquisa urgente, tarefas, contratações e administração. |
| `search_engine.py` | Gera as consultas e pesquisa na Tavily; remove duplicados e resultados sem origem. |
| `ai_analyzer.py` | Envia os resultados à Anthropic, exige JSON estruturado, valida e verifica os dados. |
| `models.py` | Listas de domínio (especialidades, zonas, estados), esquemas Pydantic e tabelas SQLAlchemy. |
| `database.py` | Acesso à base de dados: candidatos, contactos, notas, tarefas, entrevistas, pesquisas, fontes, histórico, contratações e utilizadores. |
| `utils.py` | Normalização, hash de palavras-passe, deteção de duplicados, distâncias e ordenação urgente. |
| `export_utils.py` | Exportação para CSV, XLSX e PDF. |

**Fluxo:** critérios na barra lateral → consultas geradas automaticamente → pesquisa na Tavily →
análise em lotes pela IA → validação (Pydantic + verificação dos contactos contra o texto da fonte) →
gravação sem duplicados → acompanhamento do candidato até à contratação.

Foram acrescentados à estrutura pedida dois ficheiros: `.streamlit/config.toml` (tema de cores) e
`.gitignore` (impede que o `.env` e a base de dados sejam partilhados por engano).

## Pré-requisitos

- Python 3.11 ou superior.
- Chave da API da Anthropic — <https://console.anthropic.com>
- Chave da API da Tavily — <https://app.tavily.com>
- Ligação à Internet.

## Instalação do Python

- **Windows:** descarregue o instalador em <https://www.python.org/downloads/> e assinale
  «Add Python to PATH» durante a instalação.
- **macOS:** `brew install python@3.12` ou o instalador de python.org.
- **Linux (Debian/Ubuntu):** `sudo apt install python3 python3-venv python3-pip`.

Confirme com `python --version` (ou `python3 --version`).

## Criação do ambiente virtual

Na pasta `tecnicos-avac-pro`:

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Instalação das dependências

```bash
pip install -r requirements.txt
```

## Configuração das chaves API

1. Copie `.env.example` para `.env`.
2. Preencha `ANTHROPIC_API_KEY` e `TAVILY_API_KEY`.

Em alternativa, cole as chaves em **🔑 Chaves API**, na barra lateral. Nesse caso ficam apenas na
memória da sessão: não são mostradas no ecrã nem guardadas na base de dados.

Opcionalmente, defina `ANTHROPIC_MODEL` para usar outro modelo (por omissão, `claude-opus-5-5`).

## Como iniciar a aplicação

```bash
streamlit run app.py
```

A aplicação abre em <http://localhost:8501>. O primeiro administrador é criado a partir de
`ADMIN_EMAIL` e `ADMIN_PASSWORD` no `.env`. Os restantes utilizadores são criados em **Administração → Utilizadores**.

## Como utilizar o dashboard

- **📊 Dashboard** — indicadores (candidatos encontrados, aprovados pela IA, score > 80 %, disponíveis
  imediatamente, contactados, entrevistas, contratados, score médio) e gráficos interativos por
  especialidade, localização, score, estado e evolução das pesquisas.
- **👷 Candidatos** — tabela com filtros; clique numa linha para abrir os detalhes.
- **🚨 Pesquisa urgente** — ordena os candidatos para uma necessidade imediata.
- **✅ Tarefas** — lembretes e ações de acompanhamento.
- **🤝 Contratações** — candidatos em decisão, entrevistas e contratações (gestor e administrador).
- **⚙️ Administração** — utilizadores, pesquisas, fontes, histórico de alterações e RGPD.

## Como fazer pesquisas

1. Na barra lateral, escolha especialidades, localização, raio, disponibilidade, tipo de contratação,
   urgência e número máximo de resultados.
2. Clique em **Procurar profissionais**.
3. Acompanhe o progresso. No fim, a aplicação indica quantos candidatos são novos, quantos eram
   duplicados e quantos resultados foram descartados (empresas, anúncios, diretórios…).
4. Em **Candidatos**, assinale «Apenas a última pesquisa» para ver só os resultados novos.

Para necessidades imediatas, use **Pesquisa urgente**: «Procurar na base de candidatos» responde de
imediato com os candidatos já guardados, por ordem de prioridade (disponibilidade imediata, score,
proximidade, competências, contacto direto e experiência); «Procurar novos candidatos com IA» lança
uma prospeção com esses critérios.

**Tempo e custo:** cada prospeção faz 6 a 10 consultas à Tavily e um pedido à Anthropic por cada
6 resultados. Com 20 resultados conte com cerca de um a dois minutos. O texto de cada página é
limitado a 6000 caracteres antes de ser enviado à IA.

## Como contactar candidatos

No detalhe do candidato, separador **📞 Contacto**:

1. Copie o telefone ou o email.
2. Use os botões **Perfil original**, **Email**, **WhatsApp** ou **Telefonar** — abrem a aplicação
   correspondente. **O contacto é sempre feito por si**; a aplicação nunca envia mensagens.
3. Depois do contacto, registe o meio e o resultado em **Registar contacto efetuado** e, se quiser,
   crie um lembrete. O estado do candidato é atualizado automaticamente.

O separador **🗂️ Processo** guarda o estado, as datas, a próxima ação, a expectativa salarial, os
documentos recebidos e as observações do gestor. Em **🤝 Entrevistas e contratação** marcam-se
entrevistas e o gestor aprova, rejeita ou regista a contratação.

## Como exportar resultados

Em **Candidatos**, aplique os filtros pretendidos e use **⬇️ CSV**, **⬇️ Excel** ou **⬇️ PDF**.
Os ficheiros chamam-se, por exemplo, `candidatos_avac_2026-11-16.xlsx`, com colunas em português.
O CSV usa `;` como separador e abre diretamente no Excel.

## RGPD e utilização responsável de dados públicos

- A aplicação pesquisa apenas o índice público da Tavily. Não contorna autenticações, CAPTCHAs,
  paywalls nem restrições técnicas, e não faz recolha direta (scraping) de websites.
- Um dado estar público **não dispensa o RGPD**. Trate apenas dados profissionais, para fins de
  recrutamento, e informe o candidato no primeiro contacto sobre a origem dos dados e a finalidade.
- Respeite os termos de utilização das fontes (por exemplo, redes profissionais) e os pedidos de
  oposição ou apagamento.
- Cada candidato guarda a fonte e a data de recolha. O administrador pode **anonimizar** ou
  **eliminar** qualquer registo e rever os candidatos antigos em **Administração → RGPD**.
- A IA está instruída a não inventar dados; ainda assim, um telefone ou email só é guardado se
  constar do texto da fonte. **Confirme sempre a informação com o candidato.**
- Não são feitos contactos automáticos nem em massa.
- A nota interna completa está em **Administração → RGPD**. Não substitui aconselhamento jurídico.

## Migração para PostgreSQL

Defina `DATABASE_URL` no `.env` (ver `.env.example`) e instale o controlador
(`pip install "psycopg[binary]"`). As tabelas são criadas automaticamente no arranque.

## Problemas comuns e soluções

| Problema | Solução |
|---|---|
| «Chave API em falta» | Preencha o `.env` ou configure a chave nos Secrets do alojamento. |
| «A chave … é inválida» | Confirme que copiou a chave completa, sem espaços, e que está ativa. |
| «Limite de pedidos excedido» | Aguarde um minuto; reduza o número máximo de resultados ou reveja o seu plano. |
| «Nenhum resultado encontrado» | Alargue a localização, retire requisitos ou escolha especialidades mais gerais. |
| «Tempo de resposta excedido» | Repita a pesquisa; se persistir, reduza o número máximo de resultados. |
| «JSON inválido» num lote | Os restantes lotes são aproveitados; repita a pesquisa para tentar de novo. |
| `streamlit` não é reconhecido | Ative o ambiente virtual ou use `python -m streamlit run app.py`. |
| Erro ao ativar o ambiente no Windows | Execute `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` no PowerShell. |
| Porta 8501 ocupada | `streamlit run app.py --server.port 8502` |
| Esqueci-me da palavra-passe | Outro administrador pode alterá-la em **Administração → Utilizadores**. |
| Erro na base de dados | Confirme que a pasta `data/` existe e tem permissões de escrita. |

## Próximos passos sugeridos

Registo de consentimento por candidato, integração com email/CRM, área para o próprio técnico
atualizar o perfil, avaliação após cada trabalho, notificações e pesquisa por código postal.
