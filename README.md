# Painel de acompanhamento — Projeto Algar (Binário Cloud)

Painel do projeto **BCAPI | BC Billing** da Algar (expansão do Cloud Plus), com os marcos
definidos sobre a Proposta Técnica v4.1 e as frentes combinadas com o time da Algar.

## Conteúdo
- `index.html` — o painel editável (arquivo único, sem dependências de build).
- `leitura.html` — o mesmo painel só para leitura (sem botão Editar).
- `projeto-ms-project.xml` — cronograma para abrir no Microsoft Project (salvar como .mpp).

Fonte dos dados: lista "Algar - Telecom" do ClickUp. Regra de responsável: atividade em nome do
Wagner Felix = Algar (responsável real no comentário "Responsável: ..."); o % segue a régua do
painel do Escritório de Projetos (ponderado por status, só tarefas principais).

## O que o painel mostra
- Marcos e atividades por responsável (Binário, Algar ou conjunta), com status, prazos e comentários.
- Cronograma (Gantt), carga por responsável e registro das reuniões com decisões e pendências.
- Modo edição: muda status, datas, responsável e comentários; o botão
  "Baixar para enviar à Algar" gera um novo `index.html` já atualizado.

## Como atualizar
1. Abra o painel, clique em **Editar** e faça as mudanças.
2. Clique em **Baixar para enviar à Algar**.
3. Substitua o `index.html` deste repositório pelo arquivo baixado e faça o commit.
   O Cloudflare Pages e o GitHub Pages republicam sozinhos.

> A versão interna (com itens só da Binário) **não** deve ser publicada aqui.

## Publicação
- GitHub Pages: https://wbfelix240981.github.io/binario-cloud_algar/
- Cloudflare Pages: https://binario-cloud-algar.pages.dev
