"""Sincroniza o painel da Algar com a lista "Algar - Telecom" do ClickUp.

Roda no GitHub Actions (a cada 30 min) e também à mão:
    CLICKUP_TOKEN=pk_xxx python3 automation/sync_clickup.py
    python3 automation/sync_clickup.py --from-json clickup_full.json   (teste, sem chamar a API)

O que faz:
  1. Lê todas as tarefas da lista (fases = marcos; tarefas e subtarefas = atividades), com comentários.
  2. Remonta o bloco METAS do index.html com as regras do painel:
       - atividade só em nome do Wagner Felix  -> Algar (responsável real no comentário "Responsável: ...");
       - Wagner + pessoas da Binário           -> Binário + Algar;
       - só pessoas da Binário (Diogo incluso)  -> Binário;
       - sem ninguém: subtarefa herda da tarefa-mãe; senão "A definir".
  3. Sempre renova a data/hora da "Última atualização" (como no painel de metas e no Escritório de Projetos);
     se as atividades mudaram, regrava também o bloco de dados e o XML do MS Project.
"""
import json, os, re, sys, subprocess, tempfile, time, datetime as dt, urllib.request, urllib.error

LIST_ID = "901329196221"
API = "https://api.clickup.com/api/v2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
LEITURA = os.path.join(ROOT, "leitura.html")
XML = os.path.join(ROOT, "projeto-ms-project.xml")

STATUS = {'aberto': 'backlog', 'to do': 'backlog', 'planejamento': 'in planning', 'em andamento': 'in progress',
          'in progress': 'in progress', 'revisando': 'in review', 'em revisão': 'in review', 'bloqueada': 'blocked',
          'impedimento': 'blocked', 'aguardando retorno': 'waiting', 'fechado': 'shipped', 'concluído': 'shipped',
          'concluido': 'shipped', 'complete': 'shipped', 'closed': 'shipped', 'rejeitada': 'rejected'}
NOME = {'Guilherme Soares Gomes da Silva': 'Guilherme Soares'}
PLACEHOLDER_ALGAR = 'wagner'          # quem "segura" no ClickUp as atividades da Algar

# ---------------------------------------------------------------- ClickUp
def get(path, token, tries=4):
    for i in range(tries):
        req = urllib.request.Request(API + path, headers={"Authorization": token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(5 * (i + 1)); continue
            raise RuntimeError(f"HTTP {e.code} em {path}: {e.read().decode()[:300]}")
        except urllib.error.URLError:
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"Falha repetida em {path}")

def ms(v):
    return int(v) if v not in (None, "") else None

def fetch(token):
    tasks, page = [], 0
    while True:
        d = get(f"/list/{LIST_ID}/task?include_closed=true&subtasks=true&page={page}", token)
        tasks += d.get("tasks", [])
        if d.get("last_page", True) or not d.get("tasks"):
            break
        page += 1
        if page > 30: break
    out = []
    for t in tasks:
        com = get(f"/task/{t['id']}/comment", token).get("comments", [])
        out.append({
            "id": t["id"], "parent": t.get("parent"), "name": t.get("name", ""),
            "status": (t.get("status") or {}).get("status", "").lower(),
            "start": ms(t.get("start_date")), "due": ms(t.get("due_date")),
            "assignees": [a.get("username") or a.get("email", "") for a in t.get("assignees", [])],
            "desc": (t.get("text_content") or "").strip(),
            "comments": [{"author": (c.get("user") or {}).get("username", ""), "text": c.get("comment_text", "")} for c in com],
        })
    return {"synced_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).isoformat(timespec="seconds"), "tasks": out}

# ---------------------------------------------------------------- montagem
def iso(v):
    if v is None: return None
    return (dt.datetime.fromtimestamp(v / 1000, dt.timezone.utc) - dt.timedelta(hours=3)).date().isoformat()
clean = lambda t: re.sub(r'\s+', ' ', t or '').strip()
is_algar = lambda n: (n or '').lower().startswith(PLACEHOLDER_ALGAR)

def build_metas(cu):
    T = cu["tasks"]; by = {t["id"]: t for t in T}
    tops = [t for t in T if not t["parent"] or t["parent"] not in by]
    def num(t, i):
        m = re.match(r'\s*Fase\s+(\d+)', t["name"]); return int(m.group(1)) if m else 100 + i
    phases = sorted(((num(t, i), t) for i, t in enumerate(tops)), key=lambda x: x[0])
    kids = lambda pid: sorted([t for t in T if t["parent"] == pid], key=lambda t: ((t["start"] or t["due"] or 9e15), (t["due"] or 9e15)))
    def resp_comment(t):
        for txt in [c["text"] for c in t["comments"]] + [t["desc"] or ""]:
            m = re.search(r'Respons[áa]ve(?:l|is)(?:\s+Algar)?\s*:?\s*([^\n]+)', txt, re.I)
            if m and clean(m.group(1)): return clean(m.group(1))
        return None
    def classify(t, pinfo):
        b = [NOME.get(a, a) for a in t["assignees"] if not is_algar(a)]
        w = any(is_algar(a) for a in t["assignees"]); rc = resp_comment(t)
        if w and not b: return 'algar', rc or 'Algar (a definir)'
        if w and b: return 'ambos', ' / '.join(b) + ' / ' + (rc or 'Algar')
        if b: return 'binario', ' / '.join(b)
        if rc: return 'algar', rc
        if pinfo: return pinfo
        return 'nd', 'A definir'
    metas = []
    for n, ph in phases:
        nome = clean(re.sub(r'^\s*Fase\s+\d+\s*-\s*', '', ph["name"]))
        fases = []
        def walk(pid, pinfo, subde):
            for t in kids(pid):
                p, r = classify(t, pinfo)
                it = {'n': clean(t["name"]), 'party': p, 'assignee': r, 'status': STATUS.get(t["status"], 'backlog'),
                      'start': iso(t["start"]), 'due': iso(t["due"]), 'id': t["id"]}
                if subde: it['subde'] = subde
                obs = ([clean(t["desc"])] if clean(t["desc"]) else []) + [clean(c["text"]) for c in t["comments"] if clean(c["text"])]
                if obs: it['obs'] = ' · '.join(obs)
                if it['status'] == 'rejected': it['oculto'] = True; it['status'] = 'backlog'
                if not it['due'] and subde and by[pid]["due"]:
                    it['start'] = iso(by[pid]["start"]); it['due'] = iso(by[pid]["due"])
                fases.append(it)
                walk(t["id"], (p, r), clean(t["name"]))
        walk(ph["id"], None, None)
        pa = [NOME.get(a, a) for a in ph["assignees"] if not is_algar(a)] + (['Algar'] if any(is_algar(a) for a in ph["assignees"]) else [])
        metas.append({'num': n, 'id': ph["id"], 'status': STATUS.get(ph["status"], 'backlog'), 'start': iso(ph["start"]),
                      'due': iso(ph["due"]), 'name': f'Marco {n} — {nome}', 'short': nome, 'assignee': ' / '.join(pa),
                      'tags': [], 'fases': fases})
    return metas

def main():
    args = sys.argv[1:]
    if "--from-json" in args:
        cu = json.load(open(args[args.index("--from-json") + 1]))
    else:
        token = os.environ.get("CLICKUP_TOKEN")
        if not token:
            sys.exit("ERRO: defina o secret CLICKUP_TOKEN no repositório (Settings → Secrets and variables → Actions).")
        cu = fetch(token)
    phases = [t for t in cu["tasks"] if not t["parent"]]
    if not phases:
        sys.exit("ERRO: o ClickUp não devolveu nenhuma fase; o painel não foi alterado.")
    metas = build_metas(cu)
    s = open(INDEX, encoding="utf-8").read()
    a = s.index('/* Fonte: ClickUp'); b = s.index('const METAS = [', a); e = s.index('\n];\n', b)
    corpo = 'const METAS = [\n' + ',\n'.join(' ' + json.dumps(m, ensure_ascii=False) for m in metas)
    mudou = s[b:e] != corpo
    cab = ('/* Fonte: ClickUp · lista "Algar - Telecom" (sincronização automática). Regra: atividade em nome do Wagner Felix = Algar; '
           'Diogo Lerison = Binário; responsável real no comentário "Responsável: ...". */\n')
    s = s[:a] + (cab + corpo if mudou else s[a:e]) + s[e:]
    agora = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:00Z')
    s = re.sub(r'const LAST_SYNC_UTC = "[^"]*";', f'const LAST_SYNC_UTC = "{agora}";', s, count=1)
    ro = s.replace("const SOMENTE_LEITURA = false;", "const SOMENTE_LEITURA = true;", 1).replace(
        "<title>Planejamento Algar · BCAPI | BC Billing</title>", "<title>Planejamento Algar · BCAPI | BC Billing (somente leitura)</title>", 1)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(metas, f, ensure_ascii=False); tmp = f.name
    subprocess.run([sys.executable, os.path.join(ROOT, "automation", "mspdi.py"), tmp, XML], check=True)
    # só grava os HTML depois que o XML deu certo (se algo falhar, nada fica pela metade)
    open(INDEX, "w", encoding="utf-8").write(s)
    open(LEITURA, "w", encoding="utf-8").write(ro)
    with open(os.path.join(ROOT, "last_sync.json"), "w", encoding="utf-8") as fh:
        json.dump({"utc": agora}, fh)
    lv = [f for m in metas for f in m["fases"] if not f.get("oculto")]
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh: fh.write(f"dados_mudaram={'true' if mudou else 'false'}\n")
    if not mudou:
        print("Sem mudanças nas atividades; só a data/hora da última atualização foi renovada."); return
    print(f"Painel atualizado: {len(metas)} marcos, {len(lv)} atividades, {sum(f['status']=='shipped' for f in lv)} concluídas.")

if __name__ == "__main__":
    main()
