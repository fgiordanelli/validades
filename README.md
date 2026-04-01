# Validade Fácil - V1

App simples em Streamlit para lançamento rápido de produtos com validade automática e geração de etiqueta para impressão.

## Recursos
- Login simples
- Lançamento rápido por seleção de produto
- Data e hora automáticas
- Validade automática por produto
- Histórico
- Cadastro de produtos para admin
- Backup e restauração em JSON
- Etiqueta pronta para impressão em HTML
- Arquivo `.zpl` para impressora Zebra

## Usuários de teste
- `admin` / `1234`
- `joao` / `1234`
- `maria` / `1234`

## Como rodar
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Como imprimir a etiqueta
1. Faça o lançamento do produto.
2. Clique em **Abrir etiqueta para imprimir**.
3. O navegador abre uma etiqueta no tamanho 60mm x 40mm e já chama a impressão.
4. Se usar impressora Zebra, baixe o arquivo `.zpl` e envie para a impressora/sistema compatível.

## Observação
Essa V1 ainda não usa banco de dados. Os dados ficam em memória durante a execução e podem ser salvos/restaurados por JSON.
