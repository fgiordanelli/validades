# São Validades - impressão via computador local

## Como funciona
- No celular, o usuário toca no produto.
- O app Streamlit cria um job na tabela `print_jobs`.
- No computador que está com a impressora térmica USB, rode `print_agent.py`.
- O agente lê os jobs pendentes e imprime na impressora local.

## Arquivos
- `app_streamlit_fila.py`: versão do app que envia a etiqueta para a fila online
- `print_agent.py`: agente local que roda no computador da impressora
- `print_jobs_schema.sql`: SQL para criar a tabela no Supabase

## 1) Criar a tabela no Supabase
Abra o SQL Editor do Supabase e rode o conteúdo de `print_jobs_schema.sql`.

## 2) Secrets no Streamlit Cloud
Em Settings > Secrets, adicione:

```toml
supabase_url = "https://SEU-PROJETO.supabase.co"
supabase_key = "SUA_SERVICE_ROLE_KEY"
```

O `st.secrets` lê esses valores no app Streamlit. No Community Cloud, esses segredos devem ser configurados nas settings do app, não no GitHub. citeturn665117search1turn665117search5

## 3) Dependências do app
No `requirements.txt` do app, inclua:
- streamlit
- pandas
- supabase

A biblioteca oficial Python do Supabase é `supabase-py`, usada via `from supabase import create_client`. citeturn665117search0turn665117search12

## 4) Rodar o agente no computador
### Windows
```bash
pip install supabase pywin32
set SUPABASE_URL=https://SEU-PROJETO.supabase.co
set SUPABASE_KEY=SUA_SERVICE_ROLE_KEY
set PRINTER_QUEUE=NOME_EXATO_DA_IMPRESSORA
python print_agent.py
```

### Linux / macOS
```bash
pip install supabase
export SUPABASE_URL=https://SEU-PROJETO.supabase.co
export SUPABASE_KEY=SUA_SERVICE_ROLE_KEY
export PRINTER_QUEUE=POS9220
python print_agent.py
```

No Linux/macOS, o agente usa `lp -o raw`. No Windows, usa a API de impressão do Windows via `pywin32`.

## Importante
- O computador da impressora precisa ficar ligado, com internet e com o `print_agent.py` aberto.
- A impressora USB precisa estar instalada nesse computador.
- O celular não conversa direto com a USB. Ele envia o pedido para a fila online; o computador busca o job e imprime.
